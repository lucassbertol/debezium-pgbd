# Ensaio da demonstração

Ensaio executado em 8 de novembro de 2026 no Chromium, com projeto Compose separado, volumes novos e ambos os conectores registrados conforme o README. Antes da primeira operação, os dois bancos estavam vazios, o painel Kafka aguardava o primeiro evento e o sink estava em execução.

## Ambiente usado na apresentação

A apresentação usa **somente** o ambiente descartável criado pelo inicializador. Os comandos abaixo valem para ele.

| Item | Valor |
| --- | --- |
| Subida (Windows) | `powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar-web.ps1` |
| Subida (Linux) | `./iniciar-web.sh` |
| Interface | `http://127.0.0.1:18000/` |
| API do Kafka Connect | `http://127.0.0.1:18083/` |
| Projeto Compose | `debezium-pgbd-demo-vazia` |
| `psql` da origem | `psql-origem.cmd` (Windows) ou `./psql.sh origem` (Linux) |
| `psql` do destino | `psql-destino.cmd` (Windows) ou `./psql.sh destino` (Linux) |

Os atalhos `psql-*.cmd` funcionam com duplo clique e não dependem da política de execução do PowerShell. Eles equivalem a:

```bash
docker compose -p debezium-pgbd-demo-vazia -f compose.yaml -f compose.demo.yaml exec origem psql -U postgres -d catalogo
```

Não use `docker compose exec origem ...` sem `-p` e `-f`. Esse comando aponta para o ambiente normal (porta 8000), não para o da apresentação.

## Checklist antes de subir ao palco

1. Docker Desktop aberto, em modo de contêineres Linux.
2. Rodar o inicializador e esperar `Abra http://127.0.0.1:18000/`.
3. Abrir a interface no navegador, com zoom ajustado para o projetor.
4. Abrir os dois terminais `psql` (origem e destino) e deixar lado a lado com o navegador.
5. Confirmar o selo **Em execução** no painel Destino.
6. Deixar o PPTX aberto no slide de abertura.

## Sequência para a apresentação

Mostre os três painéis lado a lado. Depois de cada ação, abra o JSON no painel Eventos para mostrar o `id` da chave, a operação e o tempo de captura exibido ao lado do evento (diferença entre `source.ts_ms`, o commit na origem, e `ts_ms`, o processamento pelo Debezium). Consulte o mesmo produto nos dois bancos antes de avançar.

| Passo | Ação | O que mostrar | Captura |
| --- | --- | --- | --- |
| 1 | Inserir Caderno, ID 101, estoque 10, pela tela. | Evento `c` para 101 e estoque 10 nos dois bancos. | [Inserção](01-insercao.png) |
| 2 | Executar `UPDATE public.produtos SET estoque = 7 WHERE id = 101;` no `psql` da origem. | Evento `u` para 101, com `before` nulo (REPLICA IDENTITY padrão) e `after` com estoque 7. Estoque 7 nos dois bancos. | [Atualização](02-atualizacao.png) |
| 3 | Abrir **Consultar banco** na origem e clicar em **Excluir** na linha 101. | Evento `d` seguido do tombstone com a mesma chave. As duas consultas retornam zero linhas. | [Exclusão](03-exclusao.png) |
| 4 | Pausar o sink, aguardar **Pausado**, inserir Caneta, ID 102, estoque 10, e abrir **Consultar banco** em cada painel. | Evento `c` para 102 e cronômetro em andamento. Uma linha na origem e zero no destino. | [Sink pausado](04-sink-pausado.png), [origem](06-consulta-origem.png) e [destino](07-consulta-destino.png) |
| 5 | Retomar o sink e aguardar **Em execução**. | A linha 102 aparece no destino com estoque 10. | [Sink retomado](05-sink-retomado.png) |

### Consultas (nos dois terminais `psql`)

```sql
SELECT id, nome, estoque FROM public.produtos WHERE id = 101;
SELECT id, nome, estoque FROM public.produtos WHERE id = 102;
```

Consulta opcional, se perguntarem sobre o slot de replicação (no `psql` da origem):

```sql
SELECT slot_name, plugin, active, confirmed_flush_lsn FROM pg_replication_slots;
```

## Recuperação durante a demonstração

Execute os comandos na pasta do projeto. No Windows PowerShell, use `curl.exe` (o `curl` do PowerShell 5.1 é um apelido de outro comando e não aceita estas opções).

```powershell
$demo = @('compose', '-p', 'debezium-pgbd-demo-vazia', '-f', 'compose.yaml', '-f', 'compose.demo.yaml')
docker @demo ps
docker @demo logs --tail=50 connect
docker @demo up -d --wait connect
curl.exe -fsS http://127.0.0.1:18083/connectors/produtos-origem/status
curl.exe -fsS http://127.0.0.1:18083/connectors/produtos-destino/status
curl.exe -fsS -X PUT http://127.0.0.1:18083/connectors/produtos-destino/resume
```

1. Rode `docker @demo ps` e veja os logs do serviço com falha. Para recriá-lo preservando os dados, use `docker @demo up -d --wait <serviço>`.
2. Consulte o status dos dois conectores. Se o sink estiver pausado, use **Retomar sink** ou o `resume` acima. Aguarde o conector e a tarefa em `RUNNING`.
3. Se um conector não existir mais, rode de novo `docker @demo exec -T web python /demo/inicializar.py`. Ele registra os dois conectores e depois confere se os painéis estão vazios. Com produtos já cadastrados, ele termina com o aviso "não iniciou vazio", que nesse caso pode ser ignorado: os conectores já foram registrados.
4. Se só a interface falhar, faça os comandos abaixo no `psql` da origem, um por vez, e consulte o destino antes de prosseguir. Para o teste assíncrono, use `curl.exe -fsS -X PUT http://127.0.0.1:18083/connectors/produtos-destino/pause` e depois `resume`.
5. Em caso de interrupção no meio da sequência, consulte primeiro os IDs 101 e 102 nos dois bancos e retome do passo correspondente. Preserve os volumes durante a recuperação.
6. Se nada funcionar, apresente os slides com as capturas do ensaio. Elas são evidências reais da solução funcionando.

```sql
INSERT INTO public.produtos (id, nome, estoque) VALUES (101, 'Caderno', 10);
UPDATE public.produtos SET estoque = 7 WHERE id = 101;
DELETE FROM public.produtos WHERE id = 101;
-- Pause o sink e confirme a pausa antes da próxima inserção.
INSERT INTO public.produtos (id, nome, estoque) VALUES (102, 'Caneta', 10);
```

## Registro do ensaio

A subida em volumes novos e o registro dos conectores levaram 30 s, com as imagens já disponíveis. A execução automatizada do roteiro técnico levou 12,6 s, incluindo interações no navegador, alteração via `psql`, consultas e sete capturas da interface atual.

O [registro de verificação](verificacao.txt) contém os tempos por passo, as chaves e operações observadas no Kafka e a saída das consultas reais nos dois bancos.

## Ensaio cronometrado da fala (preencher)

| Trecho | Previsto | Medido |
| --- | --- | --- |
| Eixo conceitual (Lucas, slides 1–8) | 8:45 | |
| Eixo técnico (Renato, slides 9–13) | 4:00 | |
| Demonstração (Renato, slides 14–20) | 7:15 | |
| Conclusão e referências (Lucas, slides 21–22) | 1:00 | |
| **Total** | **21:00** (limite de 20–25 min) | |
