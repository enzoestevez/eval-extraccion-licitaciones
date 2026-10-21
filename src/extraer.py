"""Corre una o mas variantes sobre el corpus y guarda las predicciones.

Uso:
    python src/extraer.py --variante v0-base
    python src/extraer.py --variante v2-reglas --limite 20
    python src/extraer.py --todas

Cada corrida deja data/interim/pred_<variante>.jsonl con una linea por documento:
    {"id", "datos", "tokens_in", "tokens_out", "latencia_ms", "error"}

El archivo se escribe incrementalmente y la corrida es reanudable: si la cortas
a la mitad, al volver a correr sigue desde donde quedo. Con 300 documentos y una
API que a veces falla, esto deja de ser un lujo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from proveedores import CLAVE_DE, llamar, tiene_clave  # noqa: E402
from variantes import POR_ID, VARIANTES, Variante  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
INTERMEDIO = RAIZ / "data" / "interim"
ORO = RAIZ / "data" / "gold" / "etiquetas.jsonl"

MAX_CARACTERES = 60_000  # corte de seguridad para no mandar un PDF de 400 paginas


def ids_llamados() -> set[str] | None:
    """Los avisos de convocatoria. Las adjudicaciones no se evaluan nunca."""
    indice = INTERMEDIO / "indice.json"
    if not indice.exists():
        return None
    return {
        r["id"] for r in json.loads(indice.read_text(encoding="utf-8")) if r.get("tipo") == "llamado"
    }


def cargar_corpus(solo_etiquetados: bool) -> list[tuple[str, str]]:
    """Por defecto corre solo sobre lo etiquetado, que es lo unico evaluable.

    Con --corpus-completo corre sobre todos los LLAMADOS, aunque todavia no
    esten etiquetados. Sirve para dejar las predicciones hechas mientras se
    termina de etiquetar: extraer y evaluar son pasos independientes.
    Las adjudicaciones quedan afuera en los dos casos: no entran al set de
    referencia, asi que pedirlas seria gastar llamadas en algo que nadie mide.
    """
    ids_validos = ids_llamados()
    if solo_etiquetados and ORO.exists():
        etiquetados = {
            json.loads(l)["id"] for l in ORO.read_text(encoding="utf-8").splitlines() if l.strip()
        }
        ids_validos = etiquetados if ids_validos is None else ids_validos & etiquetados

    docs = []
    for txt in sorted(INTERMEDIO.glob("*.txt")):
        if ids_validos is not None and txt.stem not in ids_validos:
            continue
        docs.append((txt.stem, txt.read_text(encoding="utf-8")[:MAX_CARACTERES]))
    return docs


def ya_hechos(destino: Path) -> set[str]:
    if not destino.exists():
        return set()
    hechos = set()
    for linea in destino.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            r = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if not r.get("error"):
            hechos.add(r["id"])
    return hechos


ESPERAS = (5, 15, 40, 90)  # segundos entre reintentos


def es_transitorio(error: str | None) -> bool:
    """¿Este error puede desaparecer solo si espero y vuelvo a intentar?

    Tres familias, todas transitorias:
      429 / RESOURCE_EXHAUSTED  -> limite de pedidos, o cuota diaria agotada
      503 / UNAVAILABLE         -> el modelo esta saturado del lado del proveedor
      ConnectError / getaddrinfo-> se corto internet un segundo

    Lo que NO se reintenta: esquema invalido, modelo inexistente, clave mala.
    Esos no mejoran esperando y hay que verlos enseguida.

    Ojo con el 429 por CUOTA DIARIA: ese no se arregla esperando 90 segundos,
    se arregla al dia siguiente. Por eso la corrida es reanudable: cortas, y
    manana volves a correr el mismo comando y sigue por donde iba.
    """
    if not error:
        return False
    e = error.lower()
    return any(
        s in e
        for s in (
            "429", "resource_exhausted", "rate limit", "quota",
            "503", "unavailable", "high demand",
            "connecterror", "getaddrinfo", "timeout", "connection",
        )
    )


def llamar_con_reintentos(v: Variante, texto: str, verboso: bool = True):
    """Llama al proveedor y reintenta si el error es transitorio.

    La capa gratuita de los proveedores limita pedidos por minuto. Con 267
    documentos por variante eso se toca seguro, y sin reintentos la corrida
    termina llena de fallos que hay que relanzar a mano.

    Solo se reintenta el limite de cuota. Un error de esquema, de modelo
    inexistente o de clave invalida no mejora esperando: se devuelve al toque
    para que lo veas y lo arregles.
    """
    r = llamar(v.proveedor, v.prompt, texto, v.modelo, temperatura=v.temperatura)
    for espera in ESPERAS:
        if not es_transitorio(r.error):
            return r
        if verboso:
            print(f"    error transitorio, espero {espera}s...", flush=True)
        time.sleep(espera)
        r = llamar(v.proveedor, v.prompt, texto, v.modelo, temperatura=v.temperatura)
    return r


def compactar(destino: Path) -> None:
    """Deja una sola linea por documento: la buena si existe, si no la del error.

    Cada reintento agrega una linea al final. Sin esto, despues de tres corridas
    el archivo tiene mas lineas de error que documentos y los conteos no se
    entienden. La informacion no se pierde: si un id fallo y despues salio bien,
    lo que importa es que salio bien.
    """
    if not destino.exists():
        return
    mejor: dict[str, dict] = {}
    for linea in destino.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            r = json.loads(linea)
        except json.JSONDecodeError:
            continue
        previo = mejor.get(r["id"])
        if previo is None or (previo.get("error") and not r.get("error")):
            mejor[r["id"]] = r
    with destino.open("w", encoding="utf-8") as f:
        for k in sorted(mejor):
            f.write(json.dumps(mejor[k], ensure_ascii=False) + "\n")


def correr(v: Variante, limite: int | None, solo_etiquetados: bool, pausa: float = 0.0) -> None:
    destino = INTERMEDIO / f"pred_{v.id}.jsonl"
    compactar(destino)
    hechos = ya_hechos(destino)
    docs = cargar_corpus(solo_etiquetados)
    pendientes = [(i, t) for i, t in docs if i not in hechos]
    if limite:
        pendientes = pendientes[:limite]

    print(f"\n{v.etiqueta}")
    print(f"  corpus {len(docs)} | ya hechos {len(hechos)} | a correr {len(pendientes)}")
    if not pendientes:
        return

    t0 = time.perf_counter()
    fallos = 0
    with destino.open("a", encoding="utf-8") as f:
        for n, (doc_id, texto) in enumerate(pendientes, 1):
            r = llamar_con_reintentos(v, texto)
            if pausa:
                time.sleep(pausa)
            if r.error:
                fallos += 1
            f.write(
                json.dumps(
                    {
                        "id": doc_id,
                        "variante": v.id,
                        "datos": r.datos,
                        "tokens_in": r.tokens_in,
                        "tokens_out": r.tokens_out,
                        "latencia_ms": r.latencia_ms,
                        "error": r.error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.flush()
            if n % 10 == 0 or n == len(pendientes):
                seg = time.perf_counter() - t0
                print(f"  {n}/{len(pendientes)}  {seg:.0f}s  fallos {fallos}", flush=True)

    if fallos:
        print(f"  {fallos} llamada(s) con error. Volve a correr para reintentarlas.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Corre variantes sobre el corpus.")
    ap.add_argument("--variante", action="append", help="id de variante (repetible)")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--limite", type=int, help="tope de documentos por variante")
    ap.add_argument(
        "--pausa",
        type=float,
        default=0.0,
        help="segundos de espera entre llamadas (util en capa gratuita, ej: 4)",
    )
    ap.add_argument(
        "--corpus-completo",
        action="store_true",
        help="correr sobre todo, no solo sobre lo etiquetado",
    )
    args = ap.parse_args()

    if args.todas:
        seleccion = list(VARIANTES)
    elif args.variante:
        try:
            seleccion = [POR_ID[i] for i in args.variante]
        except KeyError as e:
            sys.exit(f"Variante desconocida: {e}. Disponibles: {sorted(POR_ID)}")
    else:
        sys.exit("Pasa --variante <id> o --todas. Disponibles: " + ", ".join(POR_ID))

    salteadas = []
    for v in seleccion:
        if "COMPLETAR" in v.modelo:
            print(f"\n{v.id}: salteada, el modelo dice '{v.modelo}'. Completalo en variantes.py.")
            continue
        if not tiene_clave(v.proveedor):
            salteadas.append((v.id, v.proveedor, CLAVE_DE[v.proveedor]))
            continue
        correr(v, args.limite, not args.corpus_completo, args.pausa)

    if salteadas:
        print("\nVariantes salteadas por falta de clave:")
        for vid, prov, var in salteadas:
            print(f"  {vid:20} necesita {var} ({prov}) en .env")
        print(
            "\nNo es un error: podes correr el experimento sin ellas y declararlo\n"
            "en el README. Si despues conseguis la clave, volve a correr el mismo\n"
            "comando y solo se van a ejecutar las que falten."
        )


if __name__ == "__main__":
    main()
