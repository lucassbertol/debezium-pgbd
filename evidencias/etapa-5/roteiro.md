# Ensaio da demonstração

Ensaio executado em 8 de novembro de 2026 no Chromium, com projeto Compose separado, volumes novos e ambos os conectores registrados conforme o README. Antes da primeira operação, os dois bancos estavam vazios, o painel Kafka aguardava o primeiro evento e o sink estava em execução.

## Sequência para a apresentação

Mostre os três painéis lado a lado e deixe duas sessões SQL prontas. Depois de cada ação, abra o JSON no painel Eventos para mostrar o `id` da chave e a operação. Consulte o mesmo produto nos dois bancos antes de avançar.

| Passo | Ação | O que mostrar | Captura |
| --- | --- | --- | --- |
| 1 | Inserir Caderno, ID 101, estoque 10. | Evento `c` para 101 e estoque 10 nos dois bancos. | [Inserção](01-insercao.png) |
| 2 | Executar `UPDATE public.produtos SET estoque = 7 WHERE id = 101;` no `psql` da origem. | Evento `u` para 101 e estoque 7 nos dois bancos. | [Atualização](02-atualizacao.png) |
| 3 | Excluir 101. | Evento `d` seguido do tombstone com a mesma chave. As duas consultas retornam zero linhas. | [Exclusão](03-exclusao.png) |
| 4 | Pausar o sink, aguardar **Pausado** e inserir Caneta, ID 102, estoque 10. | Origem em execução, evento `c` para 102 e linha ausente no destino. | [Sink pausado](04-sink-pausado.png) |
| 5 | Retomar o sink e aguardar **Em execução**. | A linha 102 aparece no destino com estoque 10. | [Sink retomado](05-sink-retomado.png) |

### Consultas da origem

```bash
docker compose exec origem psql -U postgres -d catalogo
```

```sql
SELECT id, nome, estoque FROM public.produtos WHERE id = 101;
SELECT id, nome, estoque FROM public.produtos WHERE id = 102;
```

### Consultas do destino

```bash
docker compose exec destino psql -U postgres -d catalogo
```

```sql
SELECT id, nome, estoque FROM public.produtos WHERE id = 101;
SELECT id, nome, estoque FROM public.produtos WHERE id = 102;
```

## Recuperação durante a demonstração

1. Confira `docker compose ps` e rode `docker compose logs --tail=50 <serviço>` para o serviço com falha. Para recriá-lo preservando os dados, use `docker compose up -d --wait <serviço>`.
2. Consulte o endpoint de status dos dois conectores indicado no README. Se um estiver ausente, registre-o novamente. Se o sink estiver pausado, use **Retomar sink** ou `curl -fsS -X PUT http://127.0.0.1:8083/connectors/produtos-destino/resume`. Aguarde o conector e a tarefa em `RUNNING` antes de continuar.
3. Se só a interface falhar, faça os comandos abaixo no PostgreSQL de origem e confira o tópico com o consumidor de console do README. Execute um comando por vez e consulte o destino antes de prosseguir. Para o teste assíncrono, use a API do Connect com `pause` e depois `resume`.
4. Em caso de interrupção no meio da sequência, consulte primeiro os IDs 101 e 102 nos dois bancos. Retome do passo correspondente ao estado observado. Preserve os volumes durante a recuperação.

```sql
INSERT INTO public.produtos (id, nome, estoque) VALUES (101, 'Caderno', 10);
UPDATE public.produtos SET estoque = 7 WHERE id = 101;
DELETE FROM public.produtos WHERE id = 101;
-- Pause o sink e confirme a pausa antes da próxima inserção.
INSERT INTO public.produtos (id, nome, estoque) VALUES (102, 'Caneta', 10);
```

## Registro do ensaio

A subida em volumes novos e o registro dos conectores levaram 31 s, com as imagens já disponíveis. A execução automatizada do roteiro técnico levou 12,5 s, incluindo interações no navegador, alteração via `psql`, consultas e capturas. A fala e as transições dos slides serão cronometradas no ensaio completo.

O [registro de verificação](verificacao.txt) contém os tempos por passo, as chaves e operações observadas no Kafka e a saída das consultas reais nos dois bancos.
