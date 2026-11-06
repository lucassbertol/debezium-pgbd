# Captura de mudanças com Debezium e PostgreSQL

- **Grupo:** Lucas Bertol e Renato Marquioro
- **Disciplina:** Projeto e Gerência de Banco de Dados — 2026/2
- **Tema 10:** Captura de Mudanças de Dados em Tempo Real (Change Data Capture — CDC)
- **Status:** Proposta e roteiro de demonstração. O ambiente e as capturas de tela ainda serão produzidos.

## Proposta

Demonstrar como o Debezium captura inserções, atualizações e exclusões confirmadas em um banco PostgreSQL e como essas mudanças são aplicadas de forma assíncrona em outro PostgreSQL.

O estudo de caso é o catálogo de uma loja. O banco de origem recebe as alterações de estoque e cadastro. O banco de destino mantém uma cópia do catálogo para consultas. A demonstração usa uma única tabela, `public.produtos`, com `id` como chave primária e os campos `nome` e `estoque`. Para cada alteração, o grupo vai mostrar o comando SQL na origem, o evento gerado e o efeito da operação no destino.

## Arquitetura proposta

```text
PostgreSQL de origem
    ↓ alterações confirmadas no WAL, decodificadas com pgoutput
Conector PostgreSQL do Debezium (Kafka Connect)
    ↓ eventos de mudança
Tópico Kafka
    ↓ consumo assíncrono
Debezium JDBC Sink (Kafka Connect)
    ↓ operações SQL
PostgreSQL de destino
```

1. **PostgreSQL de origem.** Os comandos `INSERT`, `UPDATE` e `DELETE` modificam o catálogo. O PostgreSQL registra as alterações no *Write-Ahead Log* (WAL). A replicação lógica usa `wal_level=logical`, uma publicação que inclui `public.produtos` e um slot de replicação que acompanha o avanço da leitura.
2. **Conector de origem.** O Debezium usa o plugin `pgoutput` para receber mudanças confirmadas e publicá-las no Kafka. A captura ocorre sem triggers na tabela e sem consultas periódicas ao catálogo.
3. **Kafka.** O tópico separa a captura da aplicação e permite inspecionar a chave e o tipo de cada evento. O evento pode estar disponível no tópico enquanto o destino ainda apresenta o estado anterior.
4. **Conector de destino.** O Debezium JDBC Sink consome os eventos e grava no segundo PostgreSQL. A configuração proposta usa a chave do evento (`primary.key.mode=record_key`), gravações em modo `upsert` (`insert.mode=upsert`) e exclusões habilitadas (`delete.enabled=true`). O `id` identifica a linha a inserir, atualizar ou remover.

O ambiente será executado localmente com Docker Compose. O `psql` servirá para consultar os dois bancos e um consumidor de console do Kafka exibirá os eventos durante a apresentação.

### Pré-requisitos do PostgreSQL de origem

Reservar um slide do eixo técnico para explicar estes quatro pontos e conferi-los no ambiente antes do ensaio:

| Pré-requisito | O que mostrar e conferir |
| --- | --- |
| **WAL lógico** | Executar `SHOW wal_level;` e confirmar que o resultado é `logical`. |
| **Permissões** | Usar um usuário de conexão com `LOGIN` e `REPLICATION`, acesso ao banco e permissão de leitura na tabela para o snapshot inicial. |
| **Publicação** | Criar previamente uma publicação que inclua `public.produtos`. Conferir a tabela em `pg_publication_tables` e usar o mesmo nome na configuração do conector. |
| **Slot de replicação** | Configurar um nome de slot para o conector. Depois de iniciá-lo, conferir em `pg_replication_slots` se o slot pertence ao banco de origem, usa `pgoutput` e está ativo durante a captura. |

### Tabela no destino e validação do JDBC Sink

O modo `schema.evolution=basic` permite ao JDBC Sink criar a tabela de destino com base no esquema dos eventos. **Para a demonstração, a proposta é criar previamente `public.produtos` no destino e usar `schema.evolution=none`**. Assim, o grupo pode mostrar a tabela vazia antes da primeira inserção. O script de inicialização deve criar colunas com tipos compatíveis e definir `id` como chave primária. O sink deve mapear o tópico para essa tabela.

Antes da apresentação, fixar as versões das imagens usadas no Docker Compose, consultar a documentação da versão escolhida do Debezium e validar `insert.mode=upsert`, `delete.enabled=true`, `primary.key.mode=record_key` e o mapeamento de `id`. Os nomes e os comportamentos das propriedades podem variar entre versões. Confirmar que as tarefas dos conectores estão em execução e que cada operação produz o resultado esperado no destino.

No teste de exclusão, inspecionar o evento `op=d` com a chave do produto e, se habilitado no conector de origem, o *tombstone* que vem depois, com a mesma chave e valor nulo. Conferir se os registros esperados chegam ao sink com a chave preservada e se a consulta pelo `id` retorna zero linhas no destino. O JDBC Sink pode processar um evento de exclusão ou um tombstone, conforme a configuração e a versão usadas.

## Fundamentação teórica

- **Problema.** Manter uma cópia consultável do catálogo à medida que a origem muda, sem depender de uma nova cópia completa a cada alteração.
- **Conceitos.** Explicar CDC baseado em log, o papel do WAL, a decodificação lógica e a diferença entre confirmar uma transação na origem, publicar seu evento e aplicar a mudança no destino. Diferenciar também a carga inicial por *snapshot* (eventos de leitura `op=r`) do fluxo contínuo de alterações.
- **Vantagens.** A captura aproveita o log do banco e mantém o código que altera o catálogo separado do processo de sincronização. O tópico permite observar as mudanças e consumir os eventos em outro ritmo.
- **Limitações.** O destino pode ficar temporariamente defasado. Eventos podem ser reprocessados, por isso o sink usa a chave primária e `upsert` para que a reaplicação de uma gravação produza o mesmo estado. Se o conector de origem parar de avançar, o slot pode reter WAL e aumentar o uso de disco.

### Comparação com triggers e polling por timestamp

O catálogo de destino precisa refletir inserções, atualizações e exclusões da origem. As três abordagens diferem na forma de detectar essas mudanças e no trabalho necessário para entregá-las ao destino.

| Abordagem | Como funciona | O que exige ou limita |
| --- | --- | --- |
| **Triggers no PostgreSQL** | Uma trigger pode registrar cada `INSERT`, `UPDATE` e `DELETE` em uma tabela de eventos, na mesma transação que altera o catálogo. | Exige instalar e manter as triggers nas tabelas monitoradas. O registro do evento acrescenta trabalho à transação de origem, e outro processo precisa encaminhá-lo ao destino. |
| **Polling por timestamp** | Um processo consulta periodicamente a tabela pelo campo `updated_at` para buscar linhas inseridas ou atualizadas desde a última leitura. | Exige manter o timestamp atualizado e executar consultas periódicas. Mudanças sucessivas na mesma linha entre consultas podem aparecer apenas como seu estado mais recente. Uma exclusão física faz a linha desaparecer da consulta, então é preciso registrar a remoção separadamente ou usar exclusão lógica. |
| **Debezium com CDC baseado no WAL** | O conector lê as alterações confirmadas no log do PostgreSQL e publica eventos de inserção, atualização e exclusão. | Dispensa triggers de captura e consultas periódicas à tabela. Exige configurar a replicação lógica e monitorar o avanço do slot, pois atrasos na leitura podem aumentar a retenção de WAL. |

Se o estoque passar de **10 para 7 e depois para 4**, em duas transações confirmadas entre consultas, o polling pode enxergar apenas **4**. Se o produto for excluído fisicamente no mesmo intervalo, a consulta por `updated_at` não retorna essa exclusão. O Debezium pode capturar as duas atualizações e a exclusão como eventos separados. Isso permite que o grupo demonstre tanto o estado final do catálogo quanto as operações que levaram a ele.

## Demonstração ao vivo

Antes da apresentação, preparar os serviços, verificar os dois conectores e deixar abertas três sessões: SQL na origem, eventos do tópico e SQL no destino. Executar cada passo separadamente e consultar o destino pelo mesmo `id` antes de seguir.

| Passo | Ação na origem | Evento esperado | Verificação no destino |
| --- | --- | --- | --- |
| 1. Inserção | Cadastrar o produto `101` com estoque `10`. | `op=c`, com a chave `101`. | O produto aparece com estoque `10`. |
| 2. Atualização | Alterar o estoque do produto `101` para `7`. | `op=u`, com o novo estoque. | O mesmo produto aparece com estoque `7`. |
| 3. Exclusão | Excluir o produto `101`. | `op=d`, com a chave `101`. | A consulta pelo `id` retorna zero linhas. |
| 4. Sincronização assíncrona | Pausar somente o sink, confirmar a pausa e cadastrar o produto `102`. | `op=c` aparece no tópico com o sink pausado. | O produto está na origem e ainda não aparece no destino. Depois de retomar o sink, ele aparece. |

Os resultados da tabela são os critérios de sucesso da demonstração. Durante o ensaio, registrar capturas que mostrem o SQL executado, os eventos e as consultas no destino. Para o teste de pausa, guardar uma captura antes da retomada e outra depois.

## Apresentação e entrega

A avaliação divide o trabalho em **fundamentação teórica (50%)** e **demonstração prática ao vivo (50%)**. O roteiro abaixo separa a apresentação nos três eixos exigidos e reserva aproximadamente 20 minutos dentro do limite indicado no enunciado.

| Eixo | Responsável proposto | Tempo | Conteúdo |
| --- | --- | --- | --- |
| Conceitual | Lucas | 8 min | Problema, conceitos, vantagens e limitações do CDC. |
| Técnico | Renato | 4 min | Estudo de caso, diagrama do fluxo, quatro pré-requisitos do PostgreSQL de origem e configuração da tabela e do sink no destino. |
| Demonstração | Renato | 8 min | Primeiro as capturas de tela nos slides, depois a execução ao vivo e a verificação nos dois bancos. |

Cada integrante apresenta pelo menos um eixo completo. Para a entrega, o grupo deve:

- Confirmar que o tema é exclusivo na turma. A dupla respeita o limite de três integrantes.
- Enviar, por um representante, a composição do grupo e o tema escolhido ao professor (`mergen@inf.ufsm.br`).
- Ensaiar a apresentação com o ambiente em funcionamento. Mostrar o efeito de cada alteração diretamente no PostgreSQL de destino evidencia a integração exigida pelo enunciado.
- Incluir nos slides as capturas da solução funcionando, pois a avaliação considera o que foi realizado até a data de entrega.
- Entregar pelo Moodle os mesmos slides que serão apresentados. Basta um envio por grupo, na data comum a confirmar. A data da apresentação de cada grupo será divulgada com antecedência.

## Referências

- [Enunciado do trabalho](trabalho%20final.pdf)
- [Documentação do conector Debezium para PostgreSQL](https://debezium.io/documentation/reference/connectors/postgresql.html)
- [Documentação do Debezium JDBC Sink](https://debezium.io/documentation/reference/stable/connectors/jdbc.html)
