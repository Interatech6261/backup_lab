
import os
import re
import json
import shutil
import ctypes
import logging
import tkinter as tk
import urllib.request

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


# =============================================================================
# 1. CONFIGURAÇÕES GERAIS
# =============================================================================

USUARIO_REDE = "Aluno"
CAMINHOS_REDE = [
    r"\\srv\dadosalunos",
    r"\\192.168.0.27\dadosalunos"
]
CREDENCIAL_WINDOWS = "GuardaArquivosLab/Interatech6261/backup_lab"

CONFIG = {
    "rede": {
        "usuario": USUARIO_REDE,
        "senha": "",
        "caminhos": CAMINHOS_REDE.copy()
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

class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_uint32),
        ("dwHighDateTime", ctypes.c_uint32)
    ]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p)
    ]


class NETRESOURCEW(ctypes.Structure):
    _fields_ = [
        ("dwScope", ctypes.c_uint32),
        ("dwType", ctypes.c_uint32),
        ("dwDisplayType", ctypes.c_uint32),
        ("dwUsage", ctypes.c_uint32),
        ("lpLocalName", ctypes.c_wchar_p),
        ("lpRemoteName", ctypes.c_wchar_p),
        ("lpComment", ctypes.c_wchar_p),
        ("lpProvider", ctypes.c_wchar_p)
    ]


def obter_funcoes_rede():
    """Prepara as funções nativas de conexão SMB do Windows."""

    biblioteca = ctypes.WinDLL("Mpr.dll", use_last_error=True)
    conectar = biblioteca.WNetAddConnection2W
    conectar.argtypes = [
        ctypes.POINTER(NETRESOURCEW),
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32
    ]
    conectar.restype = ctypes.c_uint32

    desconectar = biblioteca.WNetCancelConnection2W
    desconectar.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_int
    ]
    desconectar.restype = ctypes.c_uint32

    return conectar, desconectar


def obter_funcoes_credenciais():
    """Prepara as funções do Gerenciador de Credenciais do Windows."""

    biblioteca = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    cred_read = biblioteca.CredReadW
    cred_read.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.POINTER(CREDENTIALW))
    ]
    cred_read.restype = ctypes.c_int

    cred_write = biblioteca.CredWriteW
    cred_write.argtypes = [ctypes.POINTER(CREDENTIALW), ctypes.c_uint32]
    cred_write.restype = ctypes.c_int

    cred_free = biblioteca.CredFree
    cred_free.argtypes = [ctypes.c_void_p]
    cred_free.restype = None

    return cred_read, cred_write, cred_free


def carregar_senha_rede():
    """Lê a senha guardada para este usuário no Windows Credential Manager."""

    cred_read, _, cred_free = obter_funcoes_credenciais()
    credencial = ctypes.POINTER(CREDENTIALW)()

    if not cred_read(CREDENCIAL_WINDOWS, 1, 0, ctypes.byref(credencial)):
        codigo_erro = ctypes.get_last_error()

        if codigo_erro == 1168:
            return None

        raise ctypes.WinError(codigo_erro)

    try:
        dados = ctypes.string_at(
            credencial.contents.CredentialBlob,
            credencial.contents.CredentialBlobSize
        )
        return dados.decode("utf-16-le")
    finally:
        cred_free(credencial)


def salvar_senha_rede(senha):
    """Guarda a senha no Windows Credential Manager para este usuário."""

    _, cred_write, _ = obter_funcoes_credenciais()
    dados = senha.encode("utf-16-le")

    if len(dados) > 2560:
        raise ValueError("A senha excede o tamanho aceito pelo Windows.")

    buffer = (ctypes.c_ubyte * len(dados)).from_buffer_copy(dados)
    credencial = CREDENTIALW(
        Flags=0,
        Type=1,
        TargetName=CREDENCIAL_WINDOWS,
        Comment="Credencial do compartilhamento do Guarda Arquivos Lab",
        LastWritten=FILETIME(),
        CredentialBlobSize=len(dados),
        CredentialBlob=ctypes.cast(
            buffer,
            ctypes.POINTER(ctypes.c_ubyte)
        ),
        Persist=2,
        AttributeCount=0,
        Attributes=None,
        TargetAlias=None,
        UserName=USUARIO_REDE
    )

    if not cred_write(ctypes.byref(credencial), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def solicitar_senha_rede():
    """Pede a senha uma vez e a salva no Windows Credential Manager."""

    janela = tk.Tk()
    janela.title("Senha do compartilhamento")
    janela.resizable(False, False)
    conteudo = ttk.Frame(janela, padding=16)
    conteudo.grid(row=0, column=0, sticky="nsew")
    conteudo.columnconfigure(0, weight=1)

    ttk.Label(
        conteudo,
        text=(
            f"Informe a senha da conta {USUARIO_REDE}. "
            "Ela será guardada no Gerenciador de Credenciais do Windows, "
            "não no script."
        ),
        wraplength=420
    ).grid(row=0, column=0, sticky="w", pady=(0, 12))

    ttk.Label(conteudo, text="Senha").grid(row=1, column=0, sticky="w")
    campo_senha = ttk.Entry(conteudo, show="*")
    campo_senha.grid(row=2, column=0, sticky="ew", pady=(2, 12))
    resultado = {"senha": None}

    def salvar_e_fechar():
        senha = campo_senha.get()

        if not senha:
            messagebox.showerror(
                "Senha obrigatória",
                "Informe a senha para continuar.",
                parent=janela
            )
            return

        try:
            salvar_senha_rede(senha)
        except (OSError, ValueError) as erro:
            messagebox.showerror(
                "Não foi possível salvar a senha",
                str(erro),
                parent=janela
            )
            return

        resultado["senha"] = senha
        janela.destroy()

    botoes = ttk.Frame(conteudo)
    botoes.grid(row=3, column=0, sticky="e")
    ttk.Button(
        botoes,
        text="Cancelar",
        command=janela.destroy
    ).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(
        botoes,
        text="Salvar e continuar",
        command=salvar_e_fechar
    ).grid(row=0, column=1)

    janela.protocol("WM_DELETE_WINDOW", janela.destroy)
    campo_senha.focus_set()
    janela.mainloop()

    return resultado["senha"]


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


def extrair_caminhos(texto, descricao):
    """Converte os caminhos de um campo multilinha em uma lista validada."""

    caminhos = [linha.strip() for linha in texto.splitlines() if linha.strip()]

    if not caminhos:
        raise ValueError(f"Informe pelo menos um caminho de {descricao}.")

    return caminhos


def solicitar_configuracao_grafica():
    """Solicita somente as pastas de origem em uma janela gráfica."""

    janela = tk.Tk()
    janela.title("Pastas para varrer")
    janela.geometry("700x520")
    janela.minsize(580, 420)
    janela.columnconfigure(0, weight=1)

    conteudo = ttk.Frame(janela, padding=16)
    conteudo.grid(row=0, column=0, sticky="nsew")
    janela.rowconfigure(0, weight=1)
    conteudo.columnconfigure(0, weight=1)
    conteudo.rowconfigure(2, weight=1)

    ttk.Label(
        conteudo,
        text=(
            "Adicione as pastas que deseja verificar. "
            "Os arquivos encontrados serão movidos para o compartilhamento."
        ),
        wraplength=640
    ).grid(row=0, column=0, sticky="w", pady=(0, 12))

    pastas = tk.Text(conteudo, height=12, wrap="none")
    pastas.grid(row=2, column=0, sticky="nsew", pady=(2, 8))

    def adicionar_pasta():
        caminho = filedialog.askdirectory(
            parent=janela,
            title="Selecione uma pasta de origem",
            mustexist=True
        )

        if caminho:
            atuais = pastas.get("1.0", "end").splitlines()

            if caminho not in atuais:
                pastas.insert("end", f"{caminho}\n")

    ttk.Button(
        conteudo,
        text="Adicionar pasta...",
        command=adicionar_pasta
    ).grid(row=1, column=0, sticky="w", pady=(0, 4))

    resultado = {"confirmado": False}

    def confirmar():
        try:
            CONFIG["monitoramento"]["pastas"] = extrair_caminhos(
                pastas.get("1.0", "end"),
                "origem"
            )
        except ValueError as erro:
            messagebox.showerror(
                "Pastas obrigatórias",
                str(erro),
                parent=janela
            )
            return

        resultado["confirmado"] = True
        janela.destroy()

    botoes = ttk.Frame(conteudo)
    botoes.grid(row=3, column=0, sticky="e")
    ttk.Button(
        botoes,
        text="Cancelar",
        command=janela.destroy
    ).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(
        botoes,
        text="Iniciar backup",
        command=confirmar
    ).grid(row=0, column=1)

    janela.protocol("WM_DELETE_WINDOW", janela.destroy)
    janela.mainloop()

    return resultado["confirmado"]


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
    Valida as pastas selecionadas pelo usuário e adiciona as pastas padrão
    do Windows e do OneDrive, se habilitadas.
    """

    logging.info("Iniciando mapeamento das pastas de origem.")

    monitoramento = CONFIG["monitoramento"]

    pastas = []

    # Pastas selecionadas pelo usuário na janela.
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
        conectar, desconectar = obter_funcoes_rede()
        desconectar(caminho, 0, 1)

        recurso = NETRESOURCEW(
            dwScope=0,
            dwType=1,
            dwDisplayType=0,
            dwUsage=0,
            lpLocalName=None,
            lpRemoteName=caminho,
            lpComment=None,
            lpProvider=None
        )
        codigo_erro = conectar(
            ctypes.byref(recurso),
            rede["senha"],
            rede["usuario"],
            0
        )

        if codigo_erro:
            logging.error(
                "Falha ao conectar em %s: %s",
                caminho,
                ctypes.FormatError(codigo_erro).strip()
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
        _, desconectar = obter_funcoes_rede()
        codigo_erro = desconectar(caminho, 0, 1)

        if codigo_erro not in (0, 2250):
            logging.error(
                "Falha ao desconectar %s: %s",
                caminho,
                ctypes.FormatError(codigo_erro).strip()
            )
        else:
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
    """Obtém a credencial e as pastas antes de executar o backup."""

    try:

        senha = carregar_senha_rede()

        if senha is None:
            senha = solicitar_senha_rede()

        if not senha:
            return

        CONFIG["rede"]["senha"] = senha
        validar_configuracao(CONFIG)

        if not solicitar_configuracao_grafica():
            return

        configurar_logging()

        logging.info(
            "Sistema Guarda Arquivos Lab iniciado."
        )

        try:
            varredura()
        finally:
            CONFIG["rede"]["senha"] = ""

    except ValueError as erro:

        mensagem = (
            "Não foi possível iniciar ou concluir o backup.\n\n"
            f"Motivo: {erro}\n\n"
            "Confira os dados informados e tente novamente."
        )

        messagebox.showerror(
            "Erro de Configuração",
            mensagem
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
