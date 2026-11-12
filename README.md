# Guarda Arquivos Lab

Script para Windows que identifica arquivos nas pastas monitoradas e os
organiza em um compartilhamento de rede, usando a matrícula encontrada no nome
do item.

## Requisitos

- Windows
- Python 3
- Acesso ao compartilhamento de rede de destino

## Configuração

Crie um arquivo `config.json` na mesma pasta de `backup_lab.py`:

```json
{
  "rede": {
    "usuario": "SEU_USUARIO",
    "senha": "SUA_SENHA",
    "caminhos": ["\\\\servidor\\compartilhamento"],
    "timeout_conexao": 8
  },
  "monitoramento": {
    "pastas": [],
    "incluir_pastas_padrao": true,
    "incluir_onedrive": true
  },
  "logs": {
    "url": null,
    "timeout": 10
  }
}
```

Substitua as credenciais e o caminho de rede pelos valores do seu ambiente.
O envio remoto de logs é opcional; deixe `url` como `null` para registrar
somente no console. O `config.json` é ignorado pelo Git para evitar publicar
credenciais.

## Execução

No Prompt de Comando ou PowerShell, na pasta do projeto:

```powershell
py backup_lab.py
```

## Atenção

O script **move** os itens processados: copia-os para o destino e depois remove
a origem. Teste primeiro com arquivos descartáveis e confirme a configuração e
o compartilhamento de destino antes de executar em pastas com dados reais.
