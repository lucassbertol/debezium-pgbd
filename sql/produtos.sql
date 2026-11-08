CREATE TABLE public.produtos (
    id integer PRIMARY KEY,
    nome text NOT NULL,
    estoque integer NOT NULL CHECK (estoque >= 0)
);
