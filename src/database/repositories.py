"""
Repositórios — única camada que escreve SQL de persistência.

Cada repositório recebe opcionalmente o caminho do banco, o que permite aos
testes usarem arquivos temporários sem variáveis globais.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.database.connection import consultar, consultar_um, obter_conexao, transacao
from src.database.models import (
    FonteDados,
    Imagem,
    LogAuditoria,
    Ocorrencia,
    Predicao,
    Usuario,
    Validacao,
    agora_iso,
)
from src.database.schema import Decisao, Perfil, StatusOcorrencia, TipoDado


class RegistroDuplicado(Exception):
    """Tentativa de inserir um registro que viola unicidade."""


class _Base:
    def __init__(self, caminho: str | Path | None = None) -> None:
        self.caminho = caminho

    def _conexao(self) -> sqlite3.Connection:
        return obter_conexao(self.caminho)


# --------------------------------------------------------------------- usuário
class UsuarioRepository(_Base):
    def criar(self, usuario: Usuario) -> Usuario:
        try:
            with transacao(self.caminho) as con:
                cursor = con.execute(
                    """
                    INSERT INTO usuario
                        (identificador, nome, senha_hash, perfil, ativo, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        usuario.identificador.strip().lower(),
                        usuario.nome,
                        usuario.senha_hash,
                        str(usuario.perfil),
                        int(usuario.ativo),
                        usuario.criado_em,
                    ),
                )
                usuario.id = cursor.lastrowid
        except sqlite3.IntegrityError as erro:
            raise RegistroDuplicado(f"usuário já existe: {usuario.identificador}") from erro
        return usuario

    def por_identificador(self, identificador: str) -> Usuario | None:
        linha = consultar_um(
            "SELECT * FROM usuario WHERE identificador = ?",
            (identificador.strip().lower(),),
            self.caminho,
        )
        return Usuario.de_linha(linha) if linha else None

    def por_id(self, usuario_id: int) -> Usuario | None:
        linha = consultar_um("SELECT * FROM usuario WHERE id = ?", (usuario_id,), self.caminho)
        return Usuario.de_linha(linha) if linha else None

    def listar(self) -> list[Usuario]:
        return [
            Usuario.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM usuario ORDER BY perfil, identificador", (), self.caminho
            )
        ]

    def registrar_acesso(self, usuario_id: int) -> None:
        with transacao(self.caminho) as con:
            con.execute(
                "UPDATE usuario SET ultimo_acesso = ? WHERE id = ?", (agora_iso(), usuario_id)
            )

    def definir_ativo(self, usuario_id: int, ativo: bool) -> None:
        with transacao(self.caminho) as con:
            con.execute("UPDATE usuario SET ativo = ? WHERE id = ?", (int(ativo), usuario_id))

    def contar_por_perfil(self, perfil: Perfil) -> int:
        linha = consultar_um(
            "SELECT COUNT(*) AS total FROM usuario WHERE perfil = ?", (str(perfil),), self.caminho
        )
        return int(linha["total"]) if linha else 0


# ------------------------------------------------------------------ ocorrência
class OcorrenciaRepository(_Base):
    def criar(self, ocorrencia: Ocorrencia) -> Ocorrencia:
        """
        Insere a ocorrência. Em caso de violação de unicidade de protocolo ou de
        chave de idempotência, levanta `RegistroDuplicado` (quem chama decide).
        """
        try:
            with transacao(self.caminho) as con:
                cursor = con.execute(
                    """
                    INSERT INTO ocorrencia (
                        protocolo, chave_idempotencia, data_hora_avistamento,
                        data_hora_cadastro, estado, municipio, latitude, longitude,
                        precisao_metros, origem_localizacao, profundidade, habitat,
                        quantidade_observada, descricao, origem_registro, tipo_dado,
                        status, fonte_dados_id, autoriza_publicar_imagem, contato_hash,
                        data_primeira_decisao
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ocorrencia.protocolo,
                        ocorrencia.chave_idempotencia,
                        ocorrencia.data_hora_avistamento,
                        ocorrencia.data_hora_cadastro,
                        ocorrencia.estado,
                        ocorrencia.municipio,
                        ocorrencia.latitude,
                        ocorrencia.longitude,
                        ocorrencia.precisao_metros,
                        str(ocorrencia.origem_localizacao),
                        ocorrencia.profundidade,
                        str(ocorrencia.habitat),
                        ocorrencia.quantidade_observada,
                        ocorrencia.descricao,
                        str(ocorrencia.origem_registro),
                        str(ocorrencia.tipo_dado),
                        str(ocorrencia.status),
                        ocorrencia.fonte_dados_id,
                        int(ocorrencia.autoriza_publicar_imagem),
                        ocorrencia.contato_hash,
                        ocorrencia.data_primeira_decisao,
                    ),
                )
                ocorrencia.id = cursor.lastrowid
        except sqlite3.IntegrityError as erro:
            raise RegistroDuplicado(str(erro)) from erro
        return ocorrencia

    def por_id(self, ocorrencia_id: int) -> Ocorrencia | None:
        linha = consultar_um("SELECT * FROM ocorrencia WHERE id = ?", (ocorrencia_id,), self.caminho)
        return Ocorrencia.de_linha(linha) if linha else None

    def por_protocolo(self, protocolo: str) -> Ocorrencia | None:
        linha = consultar_um(
            "SELECT * FROM ocorrencia WHERE protocolo = ?",
            (protocolo.strip().upper(),),
            self.caminho,
        )
        return Ocorrencia.de_linha(linha) if linha else None

    def por_chave_idempotencia(self, chave: str) -> Ocorrencia | None:
        linha = consultar_um(
            "SELECT * FROM ocorrencia WHERE chave_idempotencia = ?", (chave,), self.caminho
        )
        return Ocorrencia.de_linha(linha) if linha else None

    def protocolo_existe(self, protocolo: str) -> bool:
        return (
            consultar_um(
                "SELECT 1 FROM ocorrencia WHERE protocolo = ?", (protocolo,), self.caminho
            )
            is not None
        )

    def atualizar_status(
        self,
        ocorrencia_id: int,
        novo_status: StatusOcorrencia,
        marcar_primeira_decisao: bool = True,
    ) -> None:
        with transacao(self.caminho) as con:
            if marcar_primeira_decisao and novo_status in StatusOcorrencia.finais():
                con.execute(
                    """
                    UPDATE ocorrencia
                       SET status = ?,
                           data_primeira_decisao = COALESCE(data_primeira_decisao, ?)
                     WHERE id = ?
                    """,
                    (str(novo_status), agora_iso(), ocorrencia_id),
                )
            else:
                con.execute(
                    "UPDATE ocorrencia SET status = ? WHERE id = ?",
                    (str(novo_status), ocorrencia_id),
                )

    def atualizar_localizacao(
        self,
        ocorrencia_id: int,
        latitude: float | None,
        longitude: float | None,
        precisao_metros: float | None,
        origem_localizacao: str,
        estado: str | None = None,
        municipio: str | None = None,
    ) -> None:
        with transacao(self.caminho) as con:
            con.execute(
                """
                UPDATE ocorrencia
                   SET latitude = ?, longitude = ?, precisao_metros = ?,
                       origem_localizacao = ?, estado = ?, municipio = ?
                 WHERE id = ?
                """,
                (
                    latitude,
                    longitude,
                    precisao_metros,
                    origem_localizacao,
                    estado,
                    municipio,
                    ocorrencia_id,
                ),
            )

    def listar(
        self,
        status: list[str] | None = None,
        estados: list[str] | None = None,
        municipios: list[str] | None = None,
        origens: list[str] | None = None,
        tipos_dado: list[str] | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        somente_com_coordenadas: bool = False,
        limite: int | None = None,
        ordem: str = "data_hora_cadastro DESC",
    ) -> list[Ocorrencia]:
        """Listagem com filtros compostos — base das tabelas e do mapa."""
        sql = ["SELECT * FROM ocorrencia WHERE 1 = 1"]
        parametros: list = []

        def _adicionar_in(coluna: str, valores: list[str] | None) -> None:
            if valores:
                marcadores = ", ".join("?" for _ in valores)
                sql.append(f"AND {coluna} IN ({marcadores})")
                parametros.extend(valores)

        _adicionar_in("status", status)
        _adicionar_in("estado", estados)
        _adicionar_in("municipio", municipios)
        _adicionar_in("origem_registro", origens)
        _adicionar_in("tipo_dado", tipos_dado)

        if data_inicio:
            sql.append("AND date(data_hora_avistamento) >= date(?)")
            parametros.append(data_inicio)
        if data_fim:
            sql.append("AND date(data_hora_avistamento) <= date(?)")
            parametros.append(data_fim)
        if somente_com_coordenadas:
            sql.append("AND latitude IS NOT NULL AND longitude IS NOT NULL")

        ordens_permitidas = {
            "data_hora_cadastro DESC",
            "data_hora_cadastro ASC",
            "data_hora_avistamento DESC",
            "data_hora_avistamento ASC",
            "protocolo ASC",
        }
        sql.append(f"ORDER BY {ordem if ordem in ordens_permitidas else 'data_hora_cadastro DESC'}")
        if limite:
            sql.append("LIMIT ?")
            parametros.append(int(limite))

        linhas = consultar(" ".join(sql), tuple(parametros), self.caminho)
        return [Ocorrencia.de_linha(linha) for linha in linhas]

    def possiveis_duplicatas(
        self, janela_horas: int = 24, raio_graus: float = 0.01
    ) -> list[tuple[str, str]]:
        """
        Pares de protocolos suspeitos: coordenadas muito próximas na mesma
        janela temporal. Heurística operacional, não afirmação de duplicidade.
        """
        sql = """
        SELECT a.protocolo AS p1, b.protocolo AS p2
          FROM ocorrencia a
          JOIN ocorrencia b
            ON a.id < b.id
           AND a.latitude IS NOT NULL AND b.latitude IS NOT NULL
           AND ABS(a.latitude - b.latitude) <= ?
           AND ABS(a.longitude - b.longitude) <= ?
           AND ABS(julianday(a.data_hora_avistamento)
                 - julianday(b.data_hora_avistamento)) * 24 <= ?
         ORDER BY a.protocolo
        """
        linhas = consultar(sql, (raio_graus, raio_graus, janela_horas), self.caminho)
        return [(linha["p1"], linha["p2"]) for linha in linhas]

    def contar(self, tipos_dado: list[str] | None = None) -> int:
        if tipos_dado:
            marcadores = ", ".join("?" for _ in tipos_dado)
            sql = f"SELECT COUNT(*) AS t FROM ocorrencia WHERE tipo_dado IN ({marcadores})"
            linha = consultar_um(sql, tuple(tipos_dado), self.caminho)
        else:
            linha = consultar_um("SELECT COUNT(*) AS t FROM ocorrencia", (), self.caminho)
        return int(linha["t"]) if linha else 0

    def remover_demonstracao(self) -> int:
        """Remove todos os registros rotulados como demonstração."""
        with transacao(self.caminho) as con:
            cursor = con.execute(
                "DELETE FROM ocorrencia WHERE tipo_dado = ?", (str(TipoDado.DEMO),)
            )
            return cursor.rowcount


# ---------------------------------------------------------------------- imagem
class ImagemRepository(_Base):
    def criar(self, imagem: Imagem) -> Imagem:
        with transacao(self.caminho) as con:
            cursor = con.execute(
                """
                INSERT INTO imagem (
                    ocorrencia_id, identificador_arquivo, nome_original_sanitizado,
                    hash_sha256, formato, largura, altura, tamanho_bytes,
                    exif_removido, fonte, licenca, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    imagem.ocorrencia_id,
                    imagem.identificador_arquivo,
                    imagem.nome_original_sanitizado,
                    imagem.hash_sha256,
                    imagem.formato,
                    imagem.largura,
                    imagem.altura,
                    imagem.tamanho_bytes,
                    int(imagem.exif_removido),
                    imagem.fonte,
                    imagem.licenca,
                    imagem.criado_em,
                ),
            )
            imagem.id = cursor.lastrowid
        return imagem

    def por_ocorrencia(self, ocorrencia_id: int) -> list[Imagem]:
        return [
            Imagem.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM imagem WHERE ocorrencia_id = ? ORDER BY id",
                (ocorrencia_id,),
                self.caminho,
            )
        ]

    def primeira_por_ocorrencia(self, ocorrencia_id: int) -> Imagem | None:
        linha = consultar_um(
            "SELECT * FROM imagem WHERE ocorrencia_id = ? ORDER BY id LIMIT 1",
            (ocorrencia_id,),
            self.caminho,
        )
        return Imagem.de_linha(linha) if linha else None

    def por_hash(self, hash_sha256: str) -> list[Imagem]:
        return [
            Imagem.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM imagem WHERE hash_sha256 = ?", (hash_sha256,), self.caminho
            )
        ]


# -------------------------------------------------------------------- predição
class PredicaoRepository(_Base):
    def criar(self, predicao: Predicao) -> Predicao:
        with transacao(self.caminho) as con:
            cursor = con.execute(
                """
                INSERT INTO predicao (
                    ocorrencia_id, imagem_id, modelo, versao, classe, score,
                    tempo_inferencia_ms, detalhes, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    predicao.ocorrencia_id,
                    predicao.imagem_id,
                    predicao.modelo,
                    predicao.versao,
                    str(predicao.classe),
                    predicao.score,
                    predicao.tempo_inferencia_ms,
                    predicao.detalhes,
                    predicao.criado_em,
                ),
            )
            predicao.id = cursor.lastrowid
        return predicao

    def por_ocorrencia(self, ocorrencia_id: int) -> list[Predicao]:
        return [
            Predicao.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM predicao WHERE ocorrencia_id = ? ORDER BY id DESC",
                (ocorrencia_id,),
                self.caminho,
            )
        ]

    def ultima_por_ocorrencia(self, ocorrencia_id: int) -> Predicao | None:
        linha = consultar_um(
            "SELECT * FROM predicao WHERE ocorrencia_id = ? ORDER BY id DESC LIMIT 1",
            (ocorrencia_id,),
            self.caminho,
        )
        return Predicao.de_linha(linha) if linha else None

    def listar_recentes(self, limite: int = 100) -> list[Predicao]:
        return [
            Predicao.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM predicao ORDER BY id DESC LIMIT ?", (limite,), self.caminho
            )
        ]


# ------------------------------------------------------------------- validação
class ValidacaoRepository(_Base):
    def registrar(self, validacao: Validacao) -> Validacao:
        with transacao(self.caminho) as con:
            cursor = con.execute(
                """
                INSERT INTO validacao (
                    ocorrencia_id, avaliador_id, decisao, justificativa,
                    status_anterior, status_novo, data_validacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validacao.ocorrencia_id,
                    validacao.avaliador_id,
                    str(validacao.decisao),
                    validacao.justificativa,
                    str(validacao.status_anterior),
                    str(validacao.status_novo),
                    validacao.data_validacao,
                ),
            )
            validacao.id = cursor.lastrowid
        return validacao

    def historico(self, ocorrencia_id: int) -> list[Validacao]:
        return [
            Validacao.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM validacao WHERE ocorrencia_id = ? ORDER BY id",
                (ocorrencia_id,),
                self.caminho,
            )
        ]

    def contar_decisoes(self, decisao: Decisao) -> int:
        linha = consultar_um(
            "SELECT COUNT(*) AS t FROM validacao WHERE decisao = ?", (str(decisao),), self.caminho
        )
        return int(linha["t"]) if linha else 0


# ------------------------------------------------------------------- auditoria
class AuditoriaRepository(_Base):
    def registrar(
        self,
        entidade: str,
        acao: str,
        entidade_id: str | None = None,
        usuario_id: int | None = None,
        detalhes: dict | None = None,
    ) -> None:
        with transacao(self.caminho) as con:
            con.execute(
                """
                INSERT INTO log_auditoria
                    (usuario_id, entidade, entidade_id, acao, data_hora, detalhes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    usuario_id,
                    entidade,
                    entidade_id,
                    acao,
                    agora_iso(),
                    json.dumps(detalhes, ensure_ascii=False) if detalhes else None,
                ),
            )

    def listar(self, limite: int = 200) -> list[LogAuditoria]:
        linhas = consultar(
            "SELECT * FROM log_auditoria ORDER BY id DESC LIMIT ?", (limite,), self.caminho
        )
        return [
            LogAuditoria(
                id=linha["id"],
                usuario_id=linha["usuario_id"],
                entidade=linha["entidade"],
                entidade_id=linha["entidade_id"],
                acao=linha["acao"],
                data_hora=linha["data_hora"],
                detalhes=linha["detalhes"],
            )
            for linha in linhas
        ]

    def contar(self) -> int:
        linha = consultar_um("SELECT COUNT(*) AS t FROM log_auditoria", (), self.caminho)
        return int(linha["t"]) if linha else 0


# ----------------------------------------------------------------- fonte dados
class FonteDadosRepository(_Base):
    def criar(self, fonte: FonteDados) -> FonteDados:
        with transacao(self.caminho) as con:
            cursor = con.execute(
                """
                INSERT OR IGNORE INTO fonte_dados
                    (nome, url, data_importacao, licenca, tipo_fonte, observacoes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    fonte.nome,
                    fonte.url,
                    fonte.data_importacao,
                    fonte.licenca,
                    fonte.tipo_fonte,
                    fonte.observacoes,
                ),
            )
            fonte.id = cursor.lastrowid or self._id_existente(fonte)
        return fonte

    def _id_existente(self, fonte: FonteDados) -> int | None:
        linha = consultar_um(
            "SELECT id FROM fonte_dados WHERE nome = ? AND data_importacao = ?",
            (fonte.nome, fonte.data_importacao),
            self.caminho,
        )
        return int(linha["id"]) if linha else None

    def listar(self) -> list[FonteDados]:
        return [
            FonteDados.de_linha(linha)
            for linha in consultar(
                "SELECT * FROM fonte_dados ORDER BY nome", (), self.caminho
            )
        ]


# --------------------------------------------------------- eventos (rate limit)
class EventoRequisicaoRepository(_Base):
    def registrar(self, chave: str, acao: str) -> None:
        with transacao(self.caminho) as con:
            con.execute(
                "INSERT INTO evento_requisicao (chave, acao, data_hora) VALUES (?, ?, ?)",
                (chave, acao, agora_iso()),
            )

    def contar_na_janela(self, chave: str, acao: str, janela_segundos: int) -> int:
        limite = (datetime.now() - timedelta(seconds=janela_segundos)).replace(microsecond=0)
        linha = consultar_um(
            """
            SELECT COUNT(*) AS t FROM evento_requisicao
             WHERE chave = ? AND acao = ? AND data_hora >= ?
            """,
            (chave, acao, limite.isoformat()),
            self.caminho,
        )
        return int(linha["t"]) if linha else 0

    def limpar_antigos(self, dias: int = 7) -> int:
        limite = (datetime.now() - timedelta(days=dias)).replace(microsecond=0)
        with transacao(self.caminho) as con:
            cursor = con.execute(
                "DELETE FROM evento_requisicao WHERE data_hora < ?", (limite.isoformat(),)
            )
            return cursor.rowcount
