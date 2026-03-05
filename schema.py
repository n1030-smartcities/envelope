"""
schema.py — Tipos canônicos. ÚNICA fonte de verdade para todo o projeto.
Sem duplicação com calculo.py, cidade_manager.py, etc.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AfastamentoLateral:
    """
    Regra de afastamento lateral/fundos vinda da lei.

    Cálculo: max(H / divisor + acrescimo, minimo)
    Se divisor is None → valor fixo = minimo
    facultado_ate_m: até esta altura H o afastamento legal é zero
                     (mas o usuário PODE querer afastar mesmo assim)
    """
    minimo: float = 0.0
    divisor: Optional[float] = None
    acrescimo: float = 0.0
    facultado_ate_m: float = 0.0     # 0 = nunca facultado

    def calcular_legal(self, altura_m: float) -> float:
        """Afastamento mínimo EXIGIDO pela lei para esta altura."""
        if altura_m <= self.facultado_ate_m:
            return 0.0
        if self.divisor is None:
            return self.minimo
        return max(altura_m / self.divisor + self.acrescimo, self.minimo)

    def is_facultado(self, altura_m: float) -> bool:
        return altura_m <= self.facultado_ate_m


@dataclass
class Embasamento:
    permitido: bool = False
    altura_max_m: float = 9.0
    to_embasamento: Optional[float] = None   # 0–1
    pode_lateral: bool = False
    pode_fundos: bool = False
    pct_perimetro_max: float = 0.0


@dataclass
class ParametrosZona:
    """Schema canônico. Produzido pelo db_manager a partir do SQLite."""
    cidade: str
    chave: str           # chave única interna ("ZR-3", "AUAC|SA-04")
    sigla_display: str   # para UI ("ZR-3", "AUAC / SA-04")
    nome: str

    ca_basico: float
    ca_permissivel: Optional[float] = None
    gabarito_max_m: Optional[float] = None   # None = livre

    taxa_ocupacao: float = 0.50
    taxa_permeabilidade: float = 0.20
    recuo_frontal_m: float = 5.0

    afastamento: AfastamentoLateral = field(default_factory=AfastamentoLateral)
    embasamento: Embasamento = field(default_factory=Embasamento)

    fracao_minima_m2: Optional[float] = None
    observacoes: str = ""


@dataclass
class ConfigGaragem:
    usar_subsolo: bool = False
    n_subsolos: int = 0
    area_vaga_terreo_m2: float = 30.0
    area_vaga_subsolo_m2: float = 35.0


@dataclass
class ConfigSimulacao:
    zona: ParametrosZona
    altura_total_m: float
    idx_frentes: list[int]   # arestas encadeadas que formam a frente; ordem importa
    # Mapa: {idx_aresta → afastamento_metros}
    # O usuário define o valor — pode ser > ou < que o legal, inclusive 0
    afastamentos_laterais: dict[int, float]
    garagem: ConfigGaragem = field(default_factory=ConfigGaragem)
    usar_ca_permissivel: bool = False
    simular_embasamento: bool = False
    # Recuo frontal editável — None usa o valor legal da zona
    recuo_frontal_m: Optional[float] = None
    modo_retangular: bool = False

    def recuo_frontal_efetivo(self) -> float:
        if self.recuo_frontal_m is not None:
            return self.recuo_frontal_m
        return self.zona.recuo_frontal_m
