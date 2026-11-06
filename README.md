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

## Fundamentação teórica

- **Problema.** Manter uma cópia consultável do catálogo à medida que a origem muda, sem depender de uma nova cópia completa a cada alteração.
- **Conceitos.** Explicar CDC baseado em log, o papel do WAL, a decodificação lógica e a diferença entre confirmar uma transação na origem, publicar seu evento e aplicar a mudança no destino. Diferenciar também a carga inicial por *snapshot* (eventos de leitura `op=r`) do fluxo contínuo de alterações.
- **Vantagens.** A captura aproveita o log do banco e mantém o código que altera o catálogo separado do processo de sincronização. O tópico permite observar as mudanças e consumir os eventos em outro ritmo.
- **Limitações.** O destino pode ficar temporariamente defasado. Eventos podem ser reprocessados, por isso o sink usa a chave primária e `upsert` para que a reaplicação de uma gravação produza o mesmo estado. Se o conector de origem parar de avançar, o slot pode reter WAL e aumentar o uso de disco.

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
| Técnico | Renato | 4 min | Estudo de caso, diagrama do fluxo e configurações essenciais de captura e escrita. |
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
