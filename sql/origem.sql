CREATE ROLE cdc WITH LOGIN REPLICATION PASSWORD 'demo-cdc';
GRANT CONNECT ON DATABASE catalogo TO cdc;
GRANT USAGE ON SCHEMA public TO cdc;
GRANT SELECT ON public.produtos TO cdc;

CREATE PUBLICATION produtos_publicacao FOR TABLE public.produtos;
