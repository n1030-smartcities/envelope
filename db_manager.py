"""
db_manager.py — Leitura do SQLite de parâmetros.
Substitui cidade_manager.py. API mínima usada pelo app.

    mgr = DBManager("params.db")
    mgr.cidades_disponiveis()          → ["curitiba", "joinville"]
    mgr.zonas("curitiba")              → dict[chave, ParametrosZona]
    mgr.zona("joinville", "AUAC|SA-04")→ ParametrosZona
"""

from __future__ import annotations
import sqlite3
from functools import lru_cache
from schema import ParametrosZona, AfastamentoLateral, Embasamento


def _row_to_zona(r: sqlite3.Row) -> ParametrosZona:
    af = AfastamentoLateral(
        minimo=r["af_minimo"],
        divisor=r["af_divisor"],
        acrescimo=r["af_acrescimo"],
        facultado_ate_m=r["af_facultado_ate_m"],
    )
    emb = Embasamento(
        permitido=bool(r["emb_permitido"]),
        altura_max_m=r["emb_altura_max_m"],
        to_embasamento=r["emb_to"],
        pode_lateral=bool(r["emb_pode_lateral"]),
        pode_fundos=bool(r["emb_pode_fundos"]),
        pct_perimetro_max=r["emb_pct_perimetro"],
    )
    return ParametrosZona(
        cidade=r["cidade"],
        chave=r["chave"],
        sigla_display=r["sigla_display"],
        nome=r["nome"],
        ca_basico=r["ca_basico"],
        ca_permissivel=r["ca_permissivel"],
        gabarito_max_m=r["gabarito_max_m"],
        taxa_ocupacao=r["taxa_ocupacao"],
        taxa_permeabilidade=r["taxa_permeabilidade"],
        recuo_frontal_m=r["recuo_frontal_m"],
        afastamento=af,
        embasamento=emb,
        fracao_minima_m2=r["fracao_minima_m2"],
        observacoes=r["observacoes"] or "",
    )


class DBManager:
    def __init__(self, db_path: str):
        self._db = db_path
        self._cache: dict[str, dict[str, ParametrosZona]] = {}

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db)
        con.row_factory = sqlite3.Row
        return con

    def cidades_disponiveis(self) -> list[str]:
        with self._con() as con:
            return [r[0] for r in con.execute(
                "SELECT DISTINCT cidade FROM zonas ORDER BY cidade"
            )]

    def zonas(self, cidade: str) -> dict[str, ParametrosZona]:
        cidade = cidade.lower()
        if cidade in self._cache:
            return self._cache[cidade]
        with self._con() as con:
            rows = con.execute(
                "SELECT * FROM zonas WHERE cidade = ? ORDER BY chave", (cidade,)
            ).fetchall()
        result = {r["chave"]: _row_to_zona(r) for r in rows}
        self._cache[cidade] = result
        return result

    def zona(self, cidade: str, chave: str) -> ParametrosZona:
        return self.zonas(cidade)[chave]

    def buscar(self, cidade: str, q: str) -> dict[str, ParametrosZona]:
        """Busca texto livre em chave ou nome."""
        q = q.lower()
        return {k: v for k, v in self.zonas(cidade).items()
                if q in k.lower() or q in v.nome.lower()}
