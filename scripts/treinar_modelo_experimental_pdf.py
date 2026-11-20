#!/usr/bin/env python3
"""Treinamento REAL, mas EXPLORATÓRIO, a partir das figuras do PDF do ICMBio.

IMPORTANTE: este NÃO é o treinamento científico do LionGuard. São pouquíssimas
fotos independentes, sem conjunto de teste. Não inferir desempenho em campo.
As figuras de Morris (2012) são citadas pelo plano ICMBio (2015); uso apenas
para POC privada. Verifique permissões antes de redistribuir os originais.

Uso:
  pip install -r requirements-modelo-experimental.txt
  python scripts/treinar_modelo_experimental_pdf.py --pdf /caminho/plano.pdf
  # Para complementar com imagens autorizadas em arquivos separados:
  python scripts/treinar_modelo_experimental_pdf.py --pdf plano.pdf \\
         --positivos /caminho/lionfish --negativos /caminho/outros_peixes

O modelo usa CNN pequena treinada de scratch. O script não cria 'métricas de
teste' porque nenhum teste externo válido pode ser realizado com esta base.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import torch
from torch import nn

from src.ai.preprocessing import preparar


class RedeExperimental(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
        )
        self.classifier = nn.Linear(64, 2)

    def forward(self, x):
        return self.classifier(self.features(x))


def _img_pdf(doc, xref: int) -> Image.Image:
    return Image.open(io.BytesIO(doc.extract_image(xref)['image'])).convert('RGB')


def obter_amostras_pdf(path: Path):
    """Cortes identificados visualmente das figuras específicas do PDF enviado."""
    doc = fitz.open(str(path))
    fontes = {
        14: _img_pdf(doc, 14), 16: _img_pdf(doc, 16),
        20: _img_pdf(doc, 20), 24: _img_pdf(doc, 24),
        32: _img_pdf(doc, 32), 36: _img_pdf(doc, 36),
        42: _img_pdf(doc, 42),
    }
    # Mesmo xref = mesma imagem de origem. Não usar essas imagens em teste.
    recortes = [
        (1, 42, (100, 72, 412, 286), 'peixe em habitat recifal'),
        (1, 36, (30, 58, 404, 323), 'peixe com espinhos em mão com luva'),
        (1, 20, (87, 169, 275, 310), 'peixe manuseado por mergulhador'),
        (1, 14, (128, 182, 357, 345), 'peixe pequeno na rede'),
        (0, 36, (465, 4, 785, 344), 'luvas, sem peixe'),
        (0, 16, (0, 0, 236, 155), 'mergulhador e ambiente sem peixe no recorte'),
        (0, 20, (71, 0, 323, 157), 'rosto do mergulhador, sem peixe no recorte'),
        (0, 24, (420, 30, 819, 285), 'mergulhador com recipiente, sem peixe no recorte'),
        (0, 32, (0, 180, 340, 290), 'superfície do mar sem peixe visível no recorte'),
        (0, 14, (90, 0, 306, 164), 'mergulhador sem peixe no recorte'),
    ]
    imagens, meta = [], []
    for classe, xref, caixa, descricao in recortes:
        cropped = fontes[xref].crop(caixa)
        if cropped.width < 30 or cropped.height < 30:
            continue
        imagens.append((cropped, classe))
        meta.append({'origem': str(path.name), 'xref': xref, 'recorte': caixa,
                     'classe': 'peixe_leao' if classe else 'nao_peixe_leao', 'descricao': descricao})
    return imagens, meta


def adicionar_pasta(imagens, meta, path: Path | None, classe: int):
    if not path:
        return
    for p in sorted(path.glob('*')):
        if p.suffix.lower() not in ('.png', '.jpeg', '.jpg', '.webp'):
            continue
        try:
            with Image.open(p) as a:
                a.load()
                imagens.append((a.convert('RGB'), classe))
            meta.append({'origem':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                         'classe': 'peixe_leao' if classe else 'nao_peixe_leao',
                         'observacao':'Imagem fornecida pelo usuário; licença e rotulagem a confirmar'})
        except (OSError, ValueError) as e:
            print(f'Ignorando arquivo inválido {p}: {e}')


def aumentar(imagem: Image.Image, rnd: random.Random):
    imagem = ImageOps.exif_transpose(imagem).convert('RGB')
    # Aumento de dados é aplicado APENAS ao treino, sem confundir com fotos novas.
    if rnd.random() < .5:
        imagem = ImageOps.mirror(imagem)
    imagem = imagem.rotate(rnd.uniform(-9, 9), resample=Image.Resampling.BILINEAR)
    imagem = ImageEnhance.Brightness(imagem).enhance(rnd.uniform(.8,1.2))
    imagem = ImageEnhance.Contrast(imagem).enhance(rnd.uniform(.85,1.15))
    b = io.BytesIO(); imagem.save(b, format='PNG')
    return torch.from_numpy(preparar(b.getvalue(), lado=96).tensor[0].copy())


def executar(args):
    torch.manual_seed(42); np.random.seed(42)
    rnd = random.Random(42)
    imagem_pares, metadados = obter_amostras_pdf(Path(args.pdf))
    adicionar_pasta(imagem_pares, metadados, Path(args.positivos) if args.positivos else None, 1)
    adicionar_pasta(imagem_pares, metadados, Path(args.negativos) if args.negativos else None, 0)
    contagens = {"peixe_leao":sum(c==1 for _,c in imagem_pares),
                 "nao_peixe_leao":sum(c==0 for _,c in imagem_pares)}
    print('AMOSTRAS ORIGINAIS (não aumentadas):',contagens,flush=True)
    if min(contagens.values()) < 2:
        raise RuntimeError('Pelo menos 2 imagens por classe são necessárias até para uma POC.')
    model = RedeExperimental()
    model.train()
    torch.set_num_threads(min(3, torch.get_num_threads()))
    optim = torch.optim.AdamW(model.parameters(), lr=.0015, weight_decay=.003)
    criterion=nn.CrossEntropyLoss()
    historico=[]
    # Reutiliza tensorizações com aumentações fixas por execução para não
    # gastar minutos decodificando PNG/PIL durante todas as épocas em CPU.
    # São aumentações do mesmo conjunto, NÃO observações independentes.
    dados_base=[]
    for imagem, classe in imagem_pares:
        for _ in range(args.aumentacoes):
            dados_base.append((aumentar(imagem, rnd),classe))
    for epoca in range(1,args.epocas+1):
        dados=list(dados_base)
        rnd.shuffle(dados)
        perdas=[]
        for idx in range(0,len(dados),args.lote):
            batch = dados[idx:idx+args.lote]
            xx=torch.stack([x for x,_ in batch]); yy=torch.tensor([y for _,y in batch])
            optim.zero_grad(set_to_none=True)
            loss=criterion(model(xx),yy)
            loss.backward()
            optim.step(); perdas.append(float(loss.item()))
        media=float(np.mean(perdas))
        historico.append({'epoca':epoca, 'perda_treino':round(media,5)})
        if epoca==1 or epoca%5==0 or epoca==args.epocas:
            print(f'Época {epoca:02d}/{args.epocas}: perda_treino={media:.4f}',flush=True)
    model.eval()
    pasta=Path(args.saida); pasta.mkdir(exist_ok=True,parents=True)
    exemplo=torch.zeros(1,3,96,96)
    trace=torch.jit.trace(model,exemplo)
    arquivo=pasta/'lionguard_experimental_icmbio.pt'
    trace.save(str(arquivo))
    card={
      'nome':'lionguard-cnn-experimental-icmbio','versao':'0.1.0-experimental',
      'arquitetura':'CNN pequena, treinada do zero em poucos recortes de figuras',
      'arquivo':arquivo.name,'formato':'torchscript','entrada':96,
      'classes':['NAO_PEIXE_LEAO','PEIXE_LEAO'], 'indice_positivo':1,
      'ativacao':'softmax','detector':False, 'arquivo_metricas':None,
      'treinado_em':datetime.now(timezone.utc).isoformat(),
      'observacoes': 'MODELO EXPERIMENTAL — NÃO VALIDADO. Poucas imagens, recortes do plano ICMBio de 2015 (figuras que citam Morris 2012). Não usar para confirmar a espécie ou guiar manejo. Scores não calibrados. Sempre revisão humana.',
    }
    (pasta/'model_card.json').write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf8')
    reports=Path(args.relatorio); reports.mkdir(exist_ok=True,parents=True)
    report={'rotulo':'TREINO EXPERIMENTAL — SEM TESTE INDEPENDENTE','original_por_classe':contagens,
            'numero_fotos_independentes':len(imagem_pares),
            'aumentacoes_por_epoca_por_foto':args.aumentacoes,
            'disponibilidade_metricas_teste':False,
            'justificativa':'Fonte única, amostra insuficiente e cortes do mesmo material; métricas de validação/teste seriam enganosas.',
            'metadados':metadados, 'historico':historico}
    (reports/'treino_experimental_icmbio.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('Modelo salvo:',arquivo,'(',arquivo.stat().st_size,'bytes)',flush=True)
    return arquivo


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdf',required=True,help='Plano do ICMBio 2015 fornecido pelo usuário')
    parser.add_argument('--positivos',help='Pasta de JPGs/PNGs de peixes-leão autorizadas e identificadas')
    parser.add_argument('--negativos',help='Pasta de JPGs/PNGs negativos: preferencialmente outros peixes')
    parser.add_argument('--saida',default='models')
    parser.add_argument('--relatorio',default='reports')
    parser.add_argument('--epocas',type=int,default=30)
    parser.add_argument('--aumentacoes',type=int,default=6)
    parser.add_argument('--lote',type=int,default=12)
    executar(parser.parse_args())
