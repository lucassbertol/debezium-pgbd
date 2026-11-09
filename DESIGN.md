# Interface do laboratório CDC

Tela única em português do Brasil para demonstração do catálogo em sala. A estrutura numerada acompanha o fluxo real de origem, Kafka e destino. Em telas estreitas, a ordem é mantida em uma coluna.

O fundo cinza-claro e o texto azul-escuro dão contraste em projeção. O verde marca controles e atividade, o âmbar distingue pausa e o vermelho destaca falhas. Tipografia do sistema para leitura e monoespaçada para chaves, estados e nomes técnicos. Os tokens ficam em `web/static/styles.css`.

A tela usa controles nativos, foco visível, tabelas semânticas e detalhes expansíveis para JSON. Cada painel distingue carregamento, vazio e falha. As operações aguardam confirmação do servidor e a pausa só aparece como confirmada quando o Connect informa que o conector e a tarefa estão pausados. O destino é atualizado por consulta ao banco.

O resultado de cada operação aparece por alguns segundos em uma notificação no canto inferior direito e fica registrado no painel correspondente. As consultas automáticas mantêm seu feedback no próprio painel.

O painel Destino cronometra a última alteração nova a partir do commit na origem (source.ts_ms). A contagem para quando a consulta ao destino encontra os valores do evento ou confirma a ausência da linha excluída, e por isso é sempre maior que o tempo de captura mostrado no painel Eventos.

A interface identifica o conector de captura do Debezium junto aos eventos e o JDBC Sink junto ao destino. Os dois estados são consultados no Kafka Connect e podem mudar independentemente.

Os painéis Origem e Destino mostram as linhas de cada banco, somente leitura e atualizadas a cada 0,3 s, para que a chegada da mudança fique visível lado a lado. As janelas Consultar banco mostram o resultado do SELECT completo. A visualização carrega ao abrir e pode ser atualizada na própria janela. Na origem, a linha oferece ações de edição de estoque e exclusão. O destino é somente leitura. O SQL executado fica em um detalhe expansível.
