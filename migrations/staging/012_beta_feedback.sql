-- MathAI Staging only: authenticated, insert-only Private Beta feedback.
begin;

create table if not exists public.beta_feedback (
  id uuid primary key default extensions.gen_random_uuid(),
  student_id uuid not null references public.learning_students(id) on delete restrict,
  context text not null check (length(btrim(context)) between 1 and 100),
  category text not null check (category in (
    'GENERAL','LOGIN','QUESTION_OUTPUT','MATH_OUTPUT','DIAGNOSTIC',
    'CAMERA_UPLOAD','PERSISTENCE','TEACHER_FEEDBACK','PARENT_REPORT','CREDITS','OTHER'
  )),
  rating smallint not null check (rating between 1 and 5),
  message text not null check (length(btrim(message)) between 1 and 2000),
  app_version text not null check (length(btrim(app_version)) between 1 and 32),
  created_at timestamptz not null default pg_catalog.now()
);
create index if not exists beta_feedback_student_created_idx
  on public.beta_feedback(student_id, created_at desc);
alter table public.beta_feedback enable row level security;
revoke all on public.beta_feedback from public, anon, authenticated;

create or replace function public.mathai_private_beta_feedback_submit(
  p_context text, p_category text, p_rating integer, p_message text, p_app_version text
) returns uuid language plpgsql security definer set search_path = '' as $$
declare fid uuid := extensions.gen_random_uuid(); sid uuid := private.current_student_id();
begin
  insert into public.beta_feedback(id,student_id,context,category,rating,message,app_version)
  values(fid,sid,btrim(p_context),upper(btrim(p_category)),p_rating,btrim(p_message),btrim(p_app_version));
  return fid;
end;
$$;
revoke all on function public.mathai_private_beta_feedback_submit(text,text,integer,text,text)
  from public, anon;
grant execute on function public.mathai_private_beta_feedback_submit(text,text,integer,text,text)
  to authenticated;

create or replace function public.mathai_staging_cleanup_beta_feedback()
returns integer language plpgsql security definer set search_path = '' as $$
declare removed integer; sid uuid := private.current_student_id();
begin
  delete from public.beta_feedback
  where student_id=sid and context like 'STAGING_SMOKE%';
  get diagnostics removed = row_count;
  return removed;
end;
$$;
revoke all on function public.mathai_staging_cleanup_beta_feedback() from public, anon;
grant execute on function public.mathai_staging_cleanup_beta_feedback() to authenticated;

commit;
