# Etapa 1 — Validar o escopo e mapear o PDF

## Enunciado e evidências previstas

As páginas referem-se ao [enunciado](trabalho%20final.pdf). As evidências abaixo serão produzidas nas etapas indicadas.

| Página | Requisito ou contexto | Etapa e evidência |
| --- | --- | --- |
| 1 | Identificação do trabalho de Projeto e Gerência de Banco de Dados, 2026/2, professor Sergio Mergen. | 6 — capa com a disciplina, o tema e os integrantes. |
| 2 | Explorar tecnologia voltada a bancos de dados. Fundamentação teórica (50%) com conceitos, problema, vantagens e limitações. Demonstração ao vivo (50%) em um cenário real. | 5–7 — ensaio do catálogo, slides de teoria e execução ao vivo. |
| 3 | Grupo com até três alunos, tema exclusivo na turma e comunicação da formação e do tema por e-mail ao professor. | 1 e 7 — composição registrada e confirmação, pelo grupo, da exclusividade e do envio. |
| 4–12 | Sugestões dos temas 1 a 9. | 1 — seleção do Tema 10, na página seguinte. |
| 13 | Tema 10. Captura de mudanças pela leitura de logs, com sincronização assíncrona sem triggers. Debezium é a tecnologia sugerida. | 2–3 e 5–6 — configuração de captura pelo WAL, eventos de inserção, atualização e exclusão e teste de pausa e retomada do sink. |
| 14 | Tema fora da lista exige avaliação e concordância do professor. | 1 e 7 — o Tema 10 já consta da lista. Se houver troca por tema externo, o grupo deve confirmar a aprovação. |
| 15 | Tecnologia de banco de dados ou ferramenta integrada diretamente a um banco. Para Debezium, é obrigatório demonstrar comunicação e manipulação de dados em conexão direta. | 2–5 — SQL na origem, eventos do Kafka e consultas SQL no destino após cada operação. |
| 16 | Apresentação em slides e demonstração prática, com limite aproximado de 20–25 minutos. Duas datas reservadas, com data de cada grupo divulgada com antecedência. | 1, 6 e 7 — data a confirmar com o grupo, roteiro de 20 minutos e ensaio completo cronometrado. |
| 17 | Três eixos. Conceitual, técnico com estudo de caso e destaques de implementação, e demonstração com capturas antes da execução ao vivo. Cada aluno deve apresentar ao menos um eixo inteiro. | 5–7 — capturas reais, diagrama e configuração nos slides, divisão dos eixos e ensaio. |
| 18 | Avaliação de clareza, domínio teórico, organização e profundidade proporcional à complexidade e ao tempo. | 5–7 — ensaio, revisão dos slides e demonstração focada no fluxo completo do CDC. |
| 19 | Um integrante entrega os mesmos slides pelo Moodle na data comum a confirmar. Só conta o trabalho realizado até a entrega, com capturas nos slides, inclusive das telas exibidas ao vivo. | 5–7 — capturas reais incorporadas ao deck final e envio pelo grupo. |

## Escopo e arquitetura escolhidos

O estudo de caso é o catálogo de uma loja. Os dois PostgreSQL terão uma tabela `public.produtos` com `id` inteiro como chave primária, `nome` textual e `estoque` inteiro. A origem recebe as escritas. O destino mantém a cópia consultável.

```text
PostgreSQL origem → WAL (pgoutput) → Debezium PostgreSQL (Kafka Connect)
                  → tópico Kafka → Debezium JDBC Sink (Kafka Connect)
                  → PostgreSQL destino
```

O Docker Compose orquestrará os dois bancos, um broker Kafka em modo KRaft, um worker Kafka Connect com os dois plugins e, na etapa 4, uma aplicação FastAPI com HTML, CSS e JavaScript. A interface altera a origem, lê ambos os bancos, mostra eventos por um consumidor dedicado e controla a pausa do sink pela API do Connect. A escrita no destino fica a cargo do sink. SQL e o consumidor de console do Kafka serão usados para verificar o fluxo e servirão de roteiro de demonstração caso a interface falhe.

O catálogo, a arquitetura local, a interface, a pausa do sink e o formato PPTX são escolhas do projeto. O roteiro proposto reserva 8 minutos para Lucas no eixo conceitual, 4 para Renato no técnico e 8 para Renato na demonstração.

## Dependências verificadas e versões propostas

| Componente | Versão proposta | Base para a escolha |
| --- | --- | --- |
| PostgreSQL de origem e destino | 17.11 | A matriz Debezium 3.4 inclui PostgreSQL 17 com `pgoutput`. [Matriz oficial](https://debezium.io/releases/3.4/) · [Release PostgreSQL 17.11](https://www.postgresql.org/docs/release/17.11/) |
| Apache Kafka | 4.1.1 | O Debezium 3.4 foi lançado com essa linha de Kafka. [Release Debezium 3.4](https://debezium.io/blog/2025/12/16/debezium-3-4-final-released/) · [Imagem oficial Kafka](https://kafka.apache.org/community/downloads/) |
| Debezium e Kafka Connect | Debezium 3.4.3.Final com o Connect da imagem oficial da série 3.4 | O Dockerfile da série instala os plugins PostgreSQL e JDBC na mesma versão. Confirmar o digest e fixá-lo no Compose durante a implementação. [Dockerfile oficial](https://raw.githubusercontent.com/debezium/container-images/main/connect/3.4/Dockerfile) |
| Aplicação web | Python 3.12 e FastAPI 0.121.3 | Python 3.12 está disponível localmente. Fixar o patch da imagem Python e as versões dos clientes PostgreSQL e Kafka na etapa 4. [Notas do FastAPI](https://fastapi.tiangolo.com/release-notes/) |

O ambiente é Linux x86-64, com Docker CLI 29.1.3, Docker Compose 2.40.3, Python 3.12.3 e `curl`. O `psql` não está no PATH do host. A verificação por SQL pode usar o `psql` dentro dos contêineres. O teste `docker info` retornou permissão negada para acessar `/var/run/docker.sock`. A compatibilidade proposta é documental. A etapa 2 precisará de acesso funcional ao daemon para validar imagens e serviços.

## Pendências do grupo

- Lucas Bertol e Renato Marquioro formam uma dupla, dentro do limite de três integrantes. A exclusividade do Tema 10 na turma foi confirmada pelo grupo.
- O grupo confirmou o envio do e-mail com a formação e o tema ao professor Sergio Mergen (`mergen@inf.ufsm.br`).
- Confirmar com o grupo se a data da apresentação e a data comum de entrega no Moodle já foram divulgadas.
