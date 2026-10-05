CREATE SEQUENCE "public"."terminal_drafts_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;
CREATE SEQUENCE "public"."terminal_sessions_id_seq" AS integer INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1 NO CYCLE;
CREATE TABLE "public"."terminal_drafts" (
  "id"                    integer NOT NULL DEFAULT nextval('public.terminal_drafts_id_seq'::regclass),
  "salon_id"              integer NOT NULL,
  "terminal_id"           integer NOT NULL,
  "terminal_name"         text    DEFAULT ''::text,
  "cart_data"             text    NOT NULL DEFAULT '{}'::text,
  "updated_by_account_id" integer DEFAULT 0,
  "updated_by_name"       text    DEFAULT ''::text,
  "updated_at"            integer NOT NULL,
  CONSTRAINT "terminal_drafts_pkey" PRIMARY KEY (id)
);
ALTER TABLE "public"."terminal_drafts"
  ENABLE ROW LEVEL SECURITY;
CREATE TABLE "public"."terminal_sessions" (
  "id"             integer NOT NULL DEFAULT nextval('public.terminal_sessions_id_seq'::regclass),
  "salon_id"       integer NOT NULL,
  "terminal_id"    integer NOT NULL,
  "tab_id"         text    NOT NULL,
  "account_id"     integer DEFAULT 0,
  "account_name"   text    DEFAULT ''::text,
  "last_heartbeat" integer NOT NULL,
  "created_at"     integer NOT NULL,
  CONSTRAINT "terminal_sessions_pkey" PRIMARY KEY (id)
);
ALTER TABLE "public"."terminal_sessions"
  ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."salon_settings"
  ADD COLUMN "session_timeout" text DEFAULT '7d'::text;
ALTER SEQUENCE "public"."terminal_drafts_id_seq" OWNED BY "public"."terminal_drafts"."id";
ALTER SEQUENCE "public"."terminal_sessions_id_seq" OWNED BY "public"."terminal_sessions"."id";
CREATE UNIQUE INDEX idx_categories_unique ON public.categories USING btree (account_id, name);
CREATE INDEX idx_terminal_drafts_salon_term ON public.terminal_drafts USING btree (salon_id, terminal_id);
CREATE INDEX idx_terminal_sessions_heartbeat ON public.terminal_sessions USING btree (last_heartbeat);
CREATE INDEX idx_terminal_sessions_salon_tab ON public.terminal_sessions USING btree (salon_id, tab_id);
GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."terminal_drafts_id_seq" TO "anon", "authenticated", "postgres", "service_role";
GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."terminal_sessions_id_seq" TO "anon", "authenticated", "postgres", "service_role";
GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."terminal_drafts" TO "anon", "authenticated", "postgres", "service_role";
GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."terminal_sessions" TO "anon", "authenticated", "postgres", "service_role";
