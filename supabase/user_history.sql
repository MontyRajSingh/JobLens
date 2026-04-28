-- JobLens Supabase user-history setup.
-- Run this in the Supabase SQL editor after creating the project.

insert into storage.buckets (id, name, public)
values ('resume-pdfs', 'resume-pdfs', false)
on conflict (id) do nothing;

create table if not exists public.saved_predictions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  input jsonb not null,
  result jsonb not null,
  created_at timestamptz default now()
);

create table if not exists public.saved_offers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  input jsonb not null,
  result jsonb not null,
  created_at timestamptz default now()
);

create table if not exists public.saved_resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  file_path text not null,
  extracted_data jsonb not null,
  gap_analysis jsonb,
  prediction_result jsonb,
  created_at timestamptz default now()
);

create table if not exists public.favorite_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  job_id bigint not null,
  job_snapshot jsonb,
  created_at timestamptz default now(),
  unique(user_id, job_id)
);

alter table public.saved_predictions enable row level security;
alter table public.saved_offers enable row level security;
alter table public.saved_resumes enable row level security;
alter table public.favorite_jobs enable row level security;

create policy "Users manage own saved predictions"
on public.saved_predictions
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users manage own saved offers"
on public.saved_offers
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users manage own saved resumes"
on public.saved_resumes
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users manage own favorite jobs"
on public.favorite_jobs
for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create policy "Users upload own resume PDFs"
on storage.objects
for insert
with check (
  bucket_id = 'resume-pdfs'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "Users read own resume PDFs"
on storage.objects
for select
using (
  bucket_id = 'resume-pdfs'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "Users delete own resume PDFs"
on storage.objects
for delete
using (
  bucket_id = 'resume-pdfs'
  and (storage.foldername(name))[1] = auth.uid()::text
);
