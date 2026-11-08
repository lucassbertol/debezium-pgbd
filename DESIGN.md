# Interface do laboratório CDC

Tela única em português do Brasil para demonstração do catálogo em sala. A estrutura numerada acompanha o fluxo real de origem, Kafka e destino. Em telas estreitas, a ordem é mantida em uma coluna.

O fundo cinza-claro e o texto azul-escuro dão contraste em projeção. O verde marca controles e atividade, o âmbar distingue pausa e o vermelho destaca falhas. Tipografia do sistema para leitura e monoespaçada para chaves, estados e nomes técnicos. Os tokens ficam em `web/static/styles.css`.

A tela usa controles nativos, foco visível, tabelas semânticas e detalhes expansíveis para JSON. Cada painel distingue carregamento, vazio e falha. As operações aguardam confirmação do servidor e a pausa só aparece como confirmada quando o Connect informa que o conector e a tarefa estão pausados. O destino é atualizado por consulta ao banco.

O resultado de cada operação aparece por alguns segundos em uma notificação no canto inferior direito e fica registrado no painel correspondente. As consultas automáticas mantêm seu feedback no próprio painel.
