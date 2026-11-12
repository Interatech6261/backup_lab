# Guarda Arquivos Lab

Script para Windows que identifica arquivos nas pastas monitoradas e os
organiza em um compartilhamento de rede, usando a matrícula encontrada no nome
do item.

## Requisitos

- Windows
- Python 3
- Acesso ao compartilhamento de rede de destino

## Configuração

Ao iniciar, o script solicita:

- usuário e senha do compartilhamento (a senha não aparece enquanto é digitada);
- um ou mais caminhos de destino na rede;
- uma ou mais pastas de origem para verificar.

Informe cada caminho em uma linha e pressione Enter em uma linha vazia para
encerrar cada lista. Esses dados são solicitados novamente em cada execução e
não são gravados pelo script. O endpoint opcional de logs continua configurável
na seção `CONFIG` no início do arquivo; use `None` para registrar somente no
console.

## Execução

No Prompt de Comando ou PowerShell, na pasta do projeto:

```powershell
py backup_lab.py
```

## Atenção

O script **move** os itens processados: copia-os para o destino e depois remove
a origem. Teste primeiro com arquivos descartáveis e confirme a configuração e
o compartilhamento de destino antes de executar em pastas com dados reais.
