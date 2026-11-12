
import os
import re
import json
import shutil
import subprocess
import ctypes
import getpass
import logging
import urllib.request

from datetime import datetime
from pathlib import Path


# =============================================================================
# 1. CONFIGURAÇÕES GERAIS
# =============================================================================

CONFIG = {
    "rede": {
        "usuario": "",
        "senha": "",
        "caminhos": [],
        "timeout_conexao": 8
    },
    "monitoramento": {
        "pastas": [],
        "incluir_pastas_padrao": False,
        "incluir_onedrive": False
    },
    "logs": {
        "url": None,
        "timeout": 10
    }
}

NOME_ARQUIVO_CONFIG = ".curso_atual.txt"

LIMITE_MATRICULA_MIN = 8000
LIMITE_MATRICULA_MAX = 10000000000

LIMITE_ITENS_RELATORIO = 15
LIMITE_TEXTO_POPUP = 500


# =============================================================================
# 2. VALIDAÇÃO DA CONFIGURAÇÃO
# =============================================================================

def solicitar_caminhos(mensagem):
    """Solicita caminhos, um por linha, até receber uma linha vazia."""

    print(mensagem)

    caminhos = []

    while True:
        caminho = input("> ").strip()

        if not caminho:
            break

        caminhos.append(caminho)

    if not caminhos:
        raise ValueError("Informe pelo menos um caminho.")

    return caminhos


def solicitar_configuracao():
    """Solicita credenciais e caminhos no início de cada execução."""

    print("Configuração do backup (os dados não serão salvos).")

    CONFIG["rede"]["usuario"] = input(
        "Usuário do compartilhamento de rede: "
    ).strip()

    CONFIG["rede"]["senha"] = getpass.getpass(
        "Senha do compartilhamento de rede: "
    )

    CONFIG["rede"]["caminhos"] = solicitar_caminhos(
        "Caminho(s) do compartilhamento de destino, um por linha. "
        "Pressione Enter em uma linha vazia para terminar:"
    )

    CONFIG["monitoramento"]["pastas"] = solicitar_caminhos(
        "Pasta(s) de origem para verificar, uma por linha. "
        "Pressione Enter em uma linha vazia para terminar:"
    )


def validar_configuracao(config):
    """
    Valida as configurações definidas no início deste arquivo.
    """

    if not isinstance(config, dict):
        raise ValueError("A configuração principal deve ser um dicionário.")

    secoes_obrigatorias = ["rede", "monitoramento", "logs"]

    for secao in secoes_obrigatorias:
        if secao not in config or not isinstance(config[secao], dict):
            raise ValueError(
                f"Seção obrigatória ausente ou inválida: '{secao}'."
            )

    rede = config["rede"]
    monitoramento = config["monitoramento"]
    logs = config["logs"]

    # Validação das credenciais e caminhos de rede.
    if not isinstance(rede.get("usuario"), str) or not rede["usuario"].strip():
        raise ValueError("Usuário da rede ausente ou inválido.")

    if not isinstance(rede.get("senha"), str) or not rede["senha"]:
        raise ValueError("Senha da rede ausente ou inválida.")

    if (
        not isinstance(rede.get("caminhos"), list)
        or not rede["caminhos"]
        or not all(isinstance(p, str) and p.strip() for p in rede["caminhos"])
    ):
        raise ValueError("A lista de caminhos de rede é inválida.")

    timeout_rede = rede.get("timeout_conexao", 8)

    if type(timeout_rede) is not int or timeout_rede <= 0:
        raise ValueError("timeout_conexao deve ser um inteiro positivo.")

    # Validação das pastas monitoradas.
    pastas = monitoramento.get("pastas", [])

    if not isinstance(pastas, list) or not all(
        isinstance(p, str) and p.strip() for p in pastas
    ):
        raise ValueError("A lista de pastas monitoradas é inválida.")

    for campo in ["incluir_pastas_padrao", "incluir_onedrive"]:
        if campo in monitoramento and type(monitoramento[campo]) is not bool:
            raise ValueError(f"'{campo}' deve receber true ou false.")

    # Validação do endpoint de logs.
    url_logs = logs.get("url")

    if url_logs is not None and (
        not isinstance(url_logs, str)
        or not url_logs.startswith(("http://", "https://"))
    ):
        raise ValueError("A URL de logs deve ser uma URL HTTP/HTTPS ou None.")

    timeout_logs = logs.get("timeout", 10)

    if (
        isinstance(timeout_logs, bool)
        or not isinstance(timeout_logs, (int, float))
        or timeout_logs <= 0
    ):
        raise ValueError("O timeout dos logs deve ser positivo.")

    logging.info("Configuração validada.")

    return config


# =============================================================================
# 3. SISTEMA DE LOGS
# =============================================================================

class RemoteLogHandler(logging.Handler):
    """
    Envia registros de log para um endpoint HTTP através de POST JSON.

    Não realiza gravação local.
    """

    def __init__(self, url, timeout=10):
        super().__init__()

        self.url = url
        self.timeout = timeout

    def emit(self, record):
        try:
            payload = {
                "timestamp": datetime.fromtimestamp(
                    record.created
                ).isoformat(),

                "level": record.levelname,
                "logger": record.name,
                "function": record.funcName,
                "message": record.getMessage()
            }

            dados = json.dumps(
                payload,
                ensure_ascii=False
            ).encode("utf-8")

            requisicao = urllib.request.Request(
                self.url,
                data=dados,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "GuardaArquivosLab/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(
                requisicao,
                timeout=self.timeout
            ) as resposta:

                if not 200 <= resposta.status < 300:
                    raise RuntimeError(
                        f"Endpoint retornou HTTP {resposta.status}"
                    )

        except Exception:
            # Evita que uma falha no envio gere outro registro de log
            # e provoque um ciclo infinito.
            self.handleError(record)


def configurar_logging():
    """Configura o console e o envio remoto de registros."""

    logger = logging.getLogger()

    logger.setLevel(logging.DEBUG)

    formato = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(funcName)s: %(message)s"
    )

    # Console: permanece disponível para diagnóstico.
    console = logging.StreamHandler()
    console.setFormatter(formato)

    logger.addHandler(console)

    # Envio remoto: habilitado somente quando houver uma URL.
    url_logs = CONFIG["logs"].get("url")

    if url_logs:
        handler_remoto = RemoteLogHandler(
            url=url_logs,
            timeout=CONFIG["logs"].get("timeout", 10)
        )

        handler_remoto.setFormatter(formato)
        logger.addHandler(handler_remoto)

        logger.info("Envio remoto de logs habilitado.")

    else:
        logging.warning(
            "URL de logs não configurada. "
            "Os registros serão exibidos somente no console."
        )


# =============================================================================
# 4. MAPEAMENTO DAS PASTAS DE ORIGEM
# =============================================================================

def obter_pastas_origem():
    """
    Combina as pastas configuradas no JSON com as pastas padrão
    do Windows e do OneDrive, conforme as opções habilitadas.
    """

    logging.info("Iniciando mapeamento das pastas de origem.")

    monitoramento = CONFIG["monitoramento"]

    pastas = []

    # Pastas definidas manualmente no JSON.
    for caminho in monitoramento.get("pastas", []):

        caminho_expandido = os.path.expandvars(
            os.path.expanduser(caminho)
        )

        pastas.append(Path(caminho_expandido))

    perfil_usuario = Path(
        os.environ.get("USERPROFILE", "")
    )

    # Pastas padrão do Windows.
    if monitoramento.get("incluir_pastas_padrao", True):

        nomes_pastas = [
            "Desktop",
            "Documents",
            "Pictures",
            "Videos",
            "3D Objects"
        ]

        pastas.extend(
            perfil_usuario / nome
            for nome in nomes_pastas
        )

    # Pastas padrão do OneDrive.
    if monitoramento.get("incluir_onedrive", True):

        caminho_onedrive = os.environ.get("OneDrive")

        if caminho_onedrive:

            pasta_onedrive = Path(caminho_onedrive)

            nomes_pastas = [
                "Desktop",
                "Documents",
                "Pictures",
                "Videos"
            ]

            pastas.extend(
                pasta_onedrive / nome
                for nome in nomes_pastas
            )

    # Remove caminhos repetidos, preservando a ordem.
    pastas_unicas = []
    caminhos_identificados = set()

    for pasta in pastas:

        identificador = os.path.normcase(
            os.path.abspath(str(pasta))
        )

        if identificador in caminhos_identificados:
            continue

        caminhos_identificados.add(identificador)

        if not pasta.exists():
            logging.warning(
                f"Pasta não encontrada ou inacessível: {pasta}"
            )
            continue

        if not pasta.is_dir():
            logging.warning(
                f"O caminho informado não é um diretório: {pasta}"
            )
            continue

        pastas_unicas.append(pasta)

        logging.info(f"Pasta monitorada: {pasta}")

    logging.info(
        f"Total de pastas válidas: {len(pastas_unicas)}"
    )

    return pastas_unicas


# =============================================================================
# 5. CONEXÃO DE REDE
# =============================================================================

def conectar_rede(caminho):
    """Estabelece conexão com um compartilhamento de rede."""

    rede = CONFIG["rede"]

    logging.info(f"Testando conexão com: {caminho}")

    pasta_rede = Path(caminho)

    if pasta_rede.exists():
        logging.info("Caminho já está acessível.")
        return True

    try:
        subprocess.run(
            ["net", "use", caminho, "/delete"],
            capture_output=True,
            text=True
        )

        processo = subprocess.Popen(
            [
                "net",
                "use",
                caminho,
                rede["senha"],
                f'/user:{rede["usuario"]}'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            processo.wait(
                timeout=rede.get("timeout_conexao", 8)
            )

        except subprocess.TimeoutExpired:
            processo.kill()

            logging.error(
                f"Timeout ao conectar em {caminho}."
            )

            return False

        if pasta_rede.exists():
            logging.info(f"Conexão estabelecida: {caminho}")
            return True

        logging.warning(
            f"Caminho ainda inacessível: {caminho}"
        )

    except Exception:
        logging.exception(
            f"Erro ao conectar na rede: {caminho}"
        )

    return False


def obter_caminho_ativo():
    """Retorna o primeiro caminho de rede disponível."""

    logging.info("Buscando compartilhamento de rede disponível.")

    for caminho in CONFIG["rede"]["caminhos"]:

        if conectar_rede(caminho):
            return caminho

    logging.error("Nenhum caminho de rede disponível.")

    return None


def desconectar_rede(caminho):
    """Desconecta o compartilhamento de rede utilizado."""

    logging.info(f"Desconectando rede: {caminho}")

    try:
        subprocess.run(
            ["net", "use", caminho, "/delete"],
            capture_output=True,
            text=True
        )

        logging.info("Rede desconectada.")

    except Exception:
        logging.exception(
            f"Erro ao desconectar: {caminho}"
        )


# =============================================================================
# 6. MATRÍCULAS E CURSOS
# =============================================================================

def validar_matricula(nome):
    """Identifica uma matrícula válida no nome do item."""

    matriculas = re.findall(r"(\d{4})", nome)

    for matricula in matriculas:

        numero = int(matricula)

        if LIMITE_MATRICULA_MIN <= numero <= LIMITE_MATRICULA_MAX:
            return str(numero)

    return None


def ler_curso_ativo(caminho_raiz, matricula):
    """Consulta o curso ativo através do arquivo de configuração."""

    arquivo_config = (
        Path(caminho_raiz)
        / matricula
        / NOME_ARQUIVO_CONFIG
    )

    if not arquivo_config.exists():
        return None

    try:
        with open(
            arquivo_config,
            "r",
            encoding="utf-8"
        ) as arquivo:

            curso = arquivo.readline().strip()

        if curso:
            logging.debug(
                f"Curso ativo encontrado para {matricula}: {curso}"
            )

            return curso

    except Exception:
        logging.exception(
            f"Erro ao consultar curso da matrícula {matricula}."
        )

    return None


# =============================================================================
# 7. RESOLUÇÃO DE CONFLITOS
# =============================================================================

def resolver_conflito(caminho_final, caminho_origem=None):
    """Evita sobrescrita de arquivos existentes."""

    destino = Path(caminho_final)

    if not destino.exists():
        return destino

    if destino.is_dir():

        logging.warning(
            f"Conflito: {destino} já existe como diretório."
        )

        return None

    if caminho_origem and Path(caminho_origem).is_file():

        origem = Path(caminho_origem)

        mesmo_tamanho = (
            origem.stat().st_size == destino.stat().st_size
        )

        datas_semelhantes = (
            abs(origem.stat().st_mtime - destino.stat().st_mtime) < 60
        )

        if mesmo_tamanho and datas_semelhantes:

            logging.info(
                f"Arquivo já existe. Ignorando: {destino.name}"
            )

            return None

    timestamp = datetime.now().strftime("%H%M%S")

    novo_destino = (
        destino.parent
        / f"{destino.stem}_COPY_{timestamp}{destino.suffix}"
    )

    tentativa = 0

    while novo_destino.exists() and tentativa < 10:

        tentativa += 1

        novo_destino = (
            destino.parent
            / f"{destino.stem}_COPY_{timestamp}_{tentativa}{destino.suffix}"
        )

    logging.info(
        f"Novo nome gerado para conflito: {novo_destino.name}"
    )

    return novo_destino


# =============================================================================
# 8. OPERAÇÕES COM ARQUIVOS
# =============================================================================

def copiar_e_remover_origem(origem, destino):
    """Copia o item para o destino e remove sua origem."""

    if origem.is_dir():

        shutil.copytree(
            origem,
            destino,
            dirs_exist_ok=True
        )

        shutil.rmtree(origem)

    else:

        shutil.copy2(origem, destino)
        origem.unlink()


def remover_destino_parcial(destino):
    """Remove uma cópia incompleta após falha no processamento."""

    if not destino.exists():
        return

    logging.warning(
        f"Removendo destino parcial: {destino}"
    )

    try:

        if destino.is_dir():
            shutil.rmtree(destino)

        else:
            destino.unlink()

    except Exception:
        logging.exception(
            f"Falha ao remover destino parcial: {destino}"
        )


# =============================================================================
# 9. PROCESSAMENTO DOS ITENS
# =============================================================================

def processar_item(item_obj, destino_raiz, estatisticas):
    """Identifica, organiza e movimenta um item."""

    item = item_obj.name

    if item.startswith(".") or item.endswith(".lnk"):
        return

    matricula = validar_matricula(item)

    if not matricula:
        return

    logging.info(
        f"Item identificado com matrícula [{matricula}]: {item}"
    )

    curso_ativo = ler_curso_ativo(
        destino_raiz,
        matricula
    )

    if curso_ativo:
        pasta_destino = destino_raiz / matricula / curso_ativo

    else:
        pasta_destino = destino_raiz / matricula

    pasta_destino.mkdir(
        parents=True,
        exist_ok=True
    )

    caminho_final = pasta_destino / item

    destino_resolvido = resolver_conflito(
        caminho_final,
        item_obj
    )

    if not destino_resolvido:

        estatisticas["ignorados"] += 1
        return

    try:

        logging.info(
            f"Movendo {item} para {pasta_destino}"
        )

        copiar_e_remover_origem(
            item_obj,
            destino_resolvido
        )

        if not destino_resolvido.exists():

            raise RuntimeError(
                "Falha desconhecida após a operação de cópia."
            )

        estatisticas["movidos"] += 1

        caminho_relativo = destino_resolvido.relative_to(
            destino_raiz
        )

        if (
            len(estatisticas["itens_movidos"])
            < LIMITE_ITENS_RELATORIO
        ):

            estatisticas["itens_movidos"].append(
                f"{item} -> {caminho_relativo}"
            )

        logging.info(
            f"Movimentação concluída: {item}"
        )

    except Exception as erro:

        estatisticas["erros"] += 1

        mensagem = f"- [{item}] {str(erro)}"

        estatisticas["detalhes_erros"].append(
            mensagem
        )

        logging.exception(
            f"Erro ao processar {item}."
        )

        remover_destino_parcial(
            destino_resolvido
        )


# =============================================================================
# 10. RELATÓRIOS
# =============================================================================

def montar_relatorio(estatisticas, destino_raiz):
    """Monta o resumo textual da execução."""

    mensagens = [
        f"Rede OK -> {destino_raiz}",
        f"Itens salvos com seguranca: {estatisticas['movidos']}"
    ]

    if estatisticas["ignorados"] > 0:
        mensagens.append(
            f"Ignorados: {estatisticas['ignorados']}"
        )

    if estatisticas["itens_movidos"]:
        mensagens.append("Itens recentes:")
        mensagens.extend(
            estatisticas["itens_movidos"]
        )

    if estatisticas["erros"] > 0:

        mensagens.append(
            f"Erros encontrados ({estatisticas['erros']}):"
        )

        mensagens.extend(
            estatisticas["detalhes_erros"]
        )

    return mensagens


def exibir_resultado(estatisticas):
    """Exibe o popup correspondente ao resultado da execução."""

    movidos = estatisticas["movidos"]
    ignorados = estatisticas["ignorados"]
    erros = estatisticas["erros"]

    if erros > 0:

        titulo = "Atencao - Sincronizacao"

        texto_erros = "\n".join(
            estatisticas["detalhes_erros"]
        )

        if len(texto_erros) > LIMITE_TEXTO_POPUP:

            texto_erros = (
                texto_erros[:LIMITE_TEXTO_POPUP]
                + "... \n(Consulte os logs remotos para ver a lista completa)."
            )

        texto = (
            "Processo finalizado com alertas.\n\n"
            f"Arquivos salvos: {movidos}\n"
            f"Arquivos ignorados: {ignorados}\n\n"
            f"Detalhes dos Erros ({erros}):\n"
            f"{texto_erros}"
        )

        icone = 48

    elif movidos > 0:

        titulo = "Sucesso - Interatech"

        texto = (
            "Processo finalizado com sucesso!\n\n"
            f"{movidos} arquivo(s) salvo(s) "
            "na rede da escola com seguranca."
        )

        icone = 64

    elif ignorados > 0:

        titulo = "Sincronizacao em Dia"

        texto = (
            "Nao ha arquivos novos.\n"
            f"{ignorados} arquivo(s) já estavam salvos "
            "no servidor da Interatech."
        )

        icone = 64

    else:

        titulo = "Varredura Concluida"

        texto = (
            "Nenhum arquivo de aluno com padrão de matrícula "
            "foi encontrado para salvar."
        )

        icone = 64

    mostrar_popup(
        titulo,
        texto,
        icone
    )


def mostrar_popup(titulo, texto, tipo=0):
    """Exibe uma mensagem nativa do Windows."""

    logging.info(
        f"Exibindo popup: [{titulo}] {texto.replace(chr(10), ' ')}"
    )

    ctypes.windll.user32.MessageBoxW(
        0,
        texto,
        titulo,
        tipo
    )


# =============================================================================
# 11. EXECUÇÃO DA VARREDURA
# =============================================================================

def varredura():
    """Coordena o processo completo de backup."""

    logging.info("Iniciando rotina de varredura e backup.")

    destino_raiz_str = obter_caminho_ativo()

    if not destino_raiz_str:

        logging.error(
            "Varredura abortada. Rede indisponível."
        )

        mostrar_popup(
            "Erro - Sincronizacao",
            "Falha de conexão.\n"
            "Não foi possível acessar a rede da Interatech "
            "para salvar os arquivos.",
            16
        )

        return

    destino_raiz = Path(destino_raiz_str)

    estatisticas = {
        "movidos": 0,
        "ignorados": 0,
        "erros": 0,
        "itens_movidos": [],
        "detalhes_erros": []
    }

    try:

        pastas_origem = obter_pastas_origem()

        for pasta in pastas_origem:

            logging.debug(
                f"Analisando pasta: {pasta}"
            )

            try:

                for item_obj in pasta.iterdir():

                    processar_item(
                        item_obj,
                        destino_raiz,
                        estatisticas
                    )

            except Exception as erro:

                estatisticas["erros"] += 1

                mensagem = (
                    f"- [PASTA: {pasta}] {str(erro)}"
                )

                estatisticas["detalhes_erros"].append(
                    mensagem
                )

                logging.exception(
                    f"Erro ao analisar a pasta {pasta}."
                )

        logging.info(
            "Resumo da varredura: "
            f"{estatisticas['movidos']} movidos, "
            f"{estatisticas['ignorados']} ignorados, "
            f"{estatisticas['erros']} erros."
        )

        mensagens = montar_relatorio(
            estatisticas,
            destino_raiz
        )

        for mensagem in mensagens:
            logging.info(f"RELATORIO: {mensagem}")

        exibir_resultado(estatisticas)

    finally:

        desconectar_rede(destino_raiz_str)

        logging.info(
            "Varredura finalizada."
        )


# =============================================================================
# 12. INICIALIZAÇÃO DO SISTEMA
# =============================================================================

def main():
    """Solicita configurações, inicializa logs e executa o backup."""

    try:

        solicitar_configuracao()

        validar_configuracao(CONFIG)

        configurar_logging()

        logging.info(
            "Sistema Guarda Arquivos Lab iniciado."
        )

        varredura()

    except ValueError as erro:

        mensagem = (
            "Não foi possível iniciar o sistema.\n\n"
            f"Motivo: {erro}\n\n"
            "Verifique a seção CONFIG no início de backup_lab.py."
        )

        print(mensagem)

        ctypes.windll.user32.MessageBoxW(
            0,
            mensagem,
            "Erro de Configuração",
            16
        )

    except Exception as erro:

        logging.exception(
            f"Erro crítico durante a execução: {erro}"
        )

        ctypes.windll.user32.MessageBoxW(
            0,
            f"Ocorreu um erro inesperado:\n\n{erro}",
            "Erro - Guarda Arquivos Lab",
            16
        )


if __name__ == "__main__":
    main()
