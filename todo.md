## Concluido
[x] Suporte a token A3 (via Playwright + Chrome headful)
[x] Cache de NSU (data->NSU e indice NSU->data)
[x] Separar notas servicos prestados e servicos tomados
[x] Busca automatica de NSU (sem entrada manual)
[x] Remocao de prompts interativos (ambiente, pasta saida, pasta PEM)
[x] Classes separadas para organizacao e indice (organize_nfse.py, nsu_index.py)
[x] Rate limiting com backoff exponencial para erro 429
[x] Extracao de CNPJ com fallback multiplos niveis (CN, OU, nome arquivo)

## Planejado
[ ] Retry com backoff para erros 502/503 (infraestrutura do governo)
[ ] Suporte a A3 em Linux (via openssl engine ou similar)
[ ] Interface grafica simples (opcional)
