"""
Treinamento do classificador de peixe-leão (Abordagem A do escopo).

Arquitetura: MobileNetV3-Large pré-treinada no ImageNet, com a camada
classificadora substituída por uma saída binária. A escolha se justifica pela
quantidade limitada de imagens disponíveis para a POC — o *transfer learning*
reaproveita as características visuais já aprendidas e exige poucas épocas —
e pelo custo de inferência baixo, compatível com uso em celular.

Estratégia em duas fases:
  1. apenas o classificador treina (extrator congelado), aprendizado 1e-3;
  2. ajuste fino dos últimos blocos convolucionais, aprendizado 1e-4.

Recursos implementados: semente controlada, *early stopping* por F1 de
validação, pesos de classe para base desbalanceada, checkpoint do melhor
estado, histórico de métricas em JSON, exportação ONNX e geração do
`model_card.json` consumido pelo serviço de inferência.

Execução:
    python scripts/treinar_modelo.py --epocas 12 --lote 32

Requer PyTorch e torchvision (ver requirements.txt). Este módulo não é
importado pela aplicação Streamlit — o app usa apenas `inference.py`.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from src.ai.preprocessing import DESVIO_IMAGENET, MEDIA_IMAGENET

CLASSES = ("nao_peixe_leao", "peixe_leao")  # índice 1 = positivo
EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png", ".webp")


@dataclass
class ConfiguracaoTreino:
    diretorio_dados: Path = Path("data/processed")
    diretorio_saida: Path = Path("models")
    diretorio_relatorios: Path = Path("reports")
    tamanho_entrada: int = 224
    lote: int = 32
    epocas_cabeca: int = 4
    epocas_ajuste_fino: int = 8
    taxa_cabeca: float = 1e-3
    taxa_ajuste_fino: float = 1e-4
    paciencia: int = 4
    semente: int = 42
    versao_modelo: str = "1.0.0"
    nome_modelo: str = "lionguard-mobilenetv3"
    trabalhadores: int = 2
    exportar_onnx: bool = True


@dataclass
class HistoricoTreino:
    epocas: list[int] = field(default_factory=list)
    perda_treino: list[float] = field(default_factory=list)
    perda_validacao: list[float] = field(default_factory=list)
    acuracia_treino: list[float] = field(default_factory=list)
    acuracia_validacao: list[float] = field(default_factory=list)
    f1_validacao: list[float] = field(default_factory=list)
    fase: list[str] = field(default_factory=list)
    taxa_aprendizado: list[float] = field(default_factory=list)


def fixar_sementes(semente: int) -> None:
    """Torna o treino reproduzível, dentro do que o backend permite."""
    import torch

    random.seed(semente)
    np.random.seed(semente)
    torch.manual_seed(semente)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(semente)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def escolher_dispositivo():
    """CUDA, depois MPS (Apple), com retorno para CPU."""
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _construir_transformacoes(tamanho: int, treino: bool):
    """
    Transformações de imagem.

    No treino aplica aumentação conservadora: espelhamento horizontal, pequena
    rotação e variação de cor. Não usa espelhamento vertical nem recortes
    agressivos, que descaracterizariam a silhueta das nadadeiras.
    """
    from torchvision import transforms

    normalizar = transforms.Normalize(mean=MEDIA_IMAGENET.tolist(), std=DESVIO_IMAGENET.tolist())
    if not treino:
        return transforms.Compose(
            [
                transforms.Resize((tamanho, tamanho)),
                transforms.ToTensor(),
                normalizar,
            ]
        )
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(tamanho, scale=(0.7, 1.0), ratio=(0.8, 1.25)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=12),
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2, hue=0.03),
            transforms.ToTensor(),
            normalizar,
            transforms.RandomErasing(p=0.15, scale=(0.02, 0.12)),
        ]
    )


def contar_imagens(diretorio: Path) -> dict[str, int]:
    """Quantas imagens existem por classe em um conjunto."""
    contagem = {}
    for classe in CLASSES:
        pasta = diretorio / classe
        contagem[classe] = (
            sum(1 for arq in pasta.iterdir() if arq.suffix.lower() in EXTENSOES_IMAGEM)
            if pasta.is_dir()
            else 0
        )
    return contagem


def construir_modelo(congelar_extrator: bool = True):
    """MobileNetV3-Large com classificador binário."""
    import torch.nn as nn
    from torchvision import models

    pesos = models.MobileNet_V3_Large_Weights.IMAGENET1K_V1
    modelo = models.mobilenet_v3_large(weights=pesos)
    if congelar_extrator:
        for parametro in modelo.features.parameters():
            parametro.requires_grad = False

    entradas = modelo.classifier[-1].in_features
    modelo.classifier[-1] = nn.Linear(entradas, len(CLASSES))
    return modelo


def _pesos_de_classe(contagem: dict[str, int]):
    """Peso inversamente proporcional à frequência, para base desbalanceada."""
    import torch

    totais = [max(1, contagem.get(classe, 0)) for classe in CLASSES]
    total = sum(totais)
    pesos = [total / (len(CLASSES) * quantidade) for quantidade in totais]
    return torch.tensor(pesos, dtype=torch.float32)


def _executar_epoca(modelo, carregador, criterio, otimizador, dispositivo, treinar: bool):
    """Uma época completa; devolve (perda média, acurácia, f1, previsões)."""
    import torch

    modelo.train() if treinar else modelo.eval()
    perda_total = 0.0
    amostras = 0
    verdadeiros: list[int] = []
    previstos: list[int] = []

    contexto = torch.enable_grad() if treinar else torch.no_grad()
    with contexto:
        for entradas, alvos in carregador:
            entradas = entradas.to(dispositivo)
            alvos = alvos.to(dispositivo)

            if treinar:
                otimizador.zero_grad(set_to_none=True)
            saidas = modelo(entradas)
            perda = criterio(saidas, alvos)
            if treinar:
                perda.backward()
                otimizador.step()

            perda_total += float(perda.item()) * entradas.size(0)
            amostras += entradas.size(0)
            verdadeiros.extend(alvos.detach().cpu().tolist())
            previstos.extend(saidas.argmax(dim=1).detach().cpu().tolist())

    from sklearn.metrics import accuracy_score, f1_score

    return (
        perda_total / max(1, amostras),
        float(accuracy_score(verdadeiros, previstos)) if verdadeiros else 0.0,
        float(f1_score(verdadeiros, previstos, zero_division=0)) if verdadeiros else 0.0,
        (verdadeiros, previstos),
    )


def treinar(config: ConfiguracaoTreino | None = None) -> dict:
    """
    Executa o treinamento completo e devolve um resumo com os caminhos gerados.

    Levanta `FileNotFoundError` quando o dataset preparado não existe — o script
    `scripts/preparar_dataset.py` precisa ser executado antes.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from torchvision.datasets import ImageFolder

    config = config or ConfiguracaoTreino()
    fixar_sementes(config.semente)
    dispositivo = escolher_dispositivo()

    treino_dir = config.diretorio_dados / "train"
    validacao_dir = config.diretorio_dados / "val"
    if not treino_dir.is_dir() or not validacao_dir.is_dir():
        raise FileNotFoundError(
            f"Dataset não encontrado em {config.diretorio_dados}. "
            "Execute `python scripts/preparar_dataset.py` primeiro."
        )

    contagem_treino = contar_imagens(treino_dir)
    contagem_validacao = contar_imagens(validacao_dir)
    if min(contagem_treino.values()) == 0:
        raise FileNotFoundError(
            f"Há classe sem imagens no conjunto de treino: {contagem_treino}"
        )

    conjunto_treino = ImageFolder(
        str(treino_dir), transform=_construir_transformacoes(config.tamanho_entrada, True)
    )
    conjunto_validacao = ImageFolder(
        str(validacao_dir), transform=_construir_transformacoes(config.tamanho_entrada, False)
    )
    # Garante que o índice 1 corresponde à classe positiva.
    if conjunto_treino.classes != list(CLASSES):
        raise ValueError(
            f"Ordem de classes inesperada: {conjunto_treino.classes}; esperado {list(CLASSES)}"
        )

    carregador_treino = DataLoader(
        conjunto_treino,
        batch_size=config.lote,
        shuffle=True,
        num_workers=config.trabalhadores,
        drop_last=False,
    )
    carregador_validacao = DataLoader(
        conjunto_validacao,
        batch_size=config.lote,
        shuffle=False,
        num_workers=config.trabalhadores,
    )

    modelo = construir_modelo(congelar_extrator=True).to(dispositivo)
    criterio = nn.CrossEntropyLoss(weight=_pesos_de_classe(contagem_treino).to(dispositivo))
    historico = HistoricoTreino()

    melhor_f1 = -1.0
    melhor_estado = None
    epocas_sem_melhora = 0
    config.diretorio_saida.mkdir(parents=True, exist_ok=True)
    config.diretorio_relatorios.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = config.diretorio_saida / "checkpoint_melhor.pt"
    inicio_total = time.perf_counter()

    fases = (
        ("cabeca", config.epocas_cabeca, config.taxa_cabeca),
        ("ajuste_fino", config.epocas_ajuste_fino, config.taxa_ajuste_fino),
    )

    numero_epoca = 0
    for nome_fase, total_epocas, taxa in fases:
        if total_epocas <= 0:
            continue
        if nome_fase == "ajuste_fino":
            # Libera os últimos blocos convolucionais para ajuste fino.
            for parametro in modelo.features[-4:].parameters():
                parametro.requires_grad = True

        parametros = [p for p in modelo.parameters() if p.requires_grad]
        otimizador = torch.optim.AdamW(parametros, lr=taxa, weight_decay=1e-4)
        escalonador = torch.optim.lr_scheduler.CosineAnnealingLR(otimizador, T_max=total_epocas)

        for _ in range(total_epocas):
            numero_epoca += 1
            perda_treino, acuracia_treino, _, _ = _executar_epoca(
                modelo, carregador_treino, criterio, otimizador, dispositivo, True
            )
            perda_validacao, acuracia_validacao, f1_validacao, _ = _executar_epoca(
                modelo, carregador_validacao, criterio, otimizador, dispositivo, False
            )
            escalonador.step()

            historico.epocas.append(numero_epoca)
            historico.fase.append(nome_fase)
            historico.perda_treino.append(round(perda_treino, 5))
            historico.perda_validacao.append(round(perda_validacao, 5))
            historico.acuracia_treino.append(round(acuracia_treino, 5))
            historico.acuracia_validacao.append(round(acuracia_validacao, 5))
            historico.f1_validacao.append(round(f1_validacao, 5))
            historico.taxa_aprendizado.append(otimizador.param_groups[0]["lr"])

            print(
                f"[{nome_fase}] época {numero_epoca:02d} "
                f"perda_treino={perda_treino:.4f} perda_val={perda_validacao:.4f} "
                f"acc_val={acuracia_validacao:.4f} f1_val={f1_validacao:.4f}",
                flush=True,
            )

            if f1_validacao > melhor_f1:
                melhor_f1 = f1_validacao
                melhor_estado = {
                    chave: valor.detach().cpu().clone()
                    for chave, valor in modelo.state_dict().items()
                }
                torch.save(melhor_estado, caminho_checkpoint)
                epocas_sem_melhora = 0
            else:
                epocas_sem_melhora += 1
                if epocas_sem_melhora >= config.paciencia:
                    print(
                        f"Early stopping: {config.paciencia} épocas sem melhora de F1.",
                        flush=True,
                    )
                    break
        else:
            continue
        break

    if melhor_estado is not None:
        modelo.load_state_dict(melhor_estado)
    modelo.eval()

    duracao_total = time.perf_counter() - inicio_total

    # ----------------------------------------------------------- exportação
    caminho_torchscript = config.diretorio_saida / "lionguard_classificador.pt"
    exemplo = torch.randn(1, 3, config.tamanho_entrada, config.tamanho_entrada)
    torch.jit.save(torch.jit.trace(modelo.cpu(), exemplo), str(caminho_torchscript))

    caminho_onnx = config.diretorio_saida / "lionguard_classificador.onnx"
    if config.exportar_onnx:
        torch.onnx.export(
            modelo.cpu(),
            exemplo,
            str(caminho_onnx),
            input_names=["entrada"],
            output_names=["logits"],
            dynamic_axes={"entrada": {0: "lote"}, "logits": {0: "lote"}},
            opset_version=17,
        )

    caminho_historico = config.diretorio_relatorios / "historico_treinamento.json"
    caminho_historico.write_text(
        json.dumps(
            {
                "configuracao": {
                    chave: str(valor) if isinstance(valor, Path) else valor
                    for chave, valor in asdict(config).items()
                },
                "dispositivo": str(dispositivo),
                "imagens_treino": contagem_treino,
                "imagens_validacao": contagem_validacao,
                "melhor_f1_validacao": round(melhor_f1, 5),
                "duracao_segundos": round(duracao_total, 1),
                "historico": asdict(historico),
                "treinado_em": datetime.now().replace(microsecond=0).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    cartao = {
        "nome": config.nome_modelo,
        "versao": config.versao_modelo,
        "arquitetura": "MobileNetV3-Large (transfer learning, ImageNet)",
        "arquivo": caminho_onnx.name if config.exportar_onnx else caminho_torchscript.name,
        "formato": "onnx" if config.exportar_onnx else "torchscript",
        "entrada": config.tamanho_entrada,
        "classes": [classe.upper() for classe in CLASSES],
        "indice_positivo": 1,
        "ativacao": "softmax",
        "detector": False,
        "arquivo_metricas": "reports/metricas_modelo.json",
        "treinado_em": datetime.now().replace(microsecond=0).isoformat(),
        "observacoes": (
            "Classificador binário. Não localiza indivíduos na imagem e não "
            "produz caixas de detecção. Scores não são probabilidades "
            "calibradas. Execute scripts/avaliar_modelo.py para gerar as "
            "métricas do conjunto de teste."
        ),
    }
    (config.diretorio_saida / "model_card.json").write_text(
        json.dumps(cartao, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "melhor_f1_validacao": round(melhor_f1, 5),
        "epocas_executadas": numero_epoca,
        "dispositivo": str(dispositivo),
        "duracao_segundos": round(duracao_total, 1),
        "modelo_onnx": str(caminho_onnx) if config.exportar_onnx else None,
        "modelo_torchscript": str(caminho_torchscript),
        "checkpoint": str(caminho_checkpoint),
        "historico": str(caminho_historico),
        "cartao_modelo": str(config.diretorio_saida / "model_card.json"),
        "imagens_treino": contagem_treino,
        "imagens_validacao": contagem_validacao,
    }
