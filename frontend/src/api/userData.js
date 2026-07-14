import { supabase } from '../lib/supabase';

function requireSupabase() {
  if (!supabase) throw new Error('Supabase is not configured.');
  return supabase;
}

export async function savePrediction(userId, input, result) {
  const client = requireSupabase();
  const { error } = await client.from('saved_predictions').insert({
    user_id: userId,
    input,
    result,
  });
  if (error) throw error;
}

export async function getFavoriteJob(userId, jobId) {
  const client = requireSupabase();
  const { data, error } = await client
    .from('favorite_jobs')
    .select('id')
    .eq('user_id', userId)
    .eq('job_id', jobId)
    .maybeSingle();
  if (error) throw error;
  return data;
}

export async function addFavoriteJob(userId, job) {
  const client = requireSupabase();
  const { error } = await client.from('favorite_jobs').upsert({
    user_id: userId,
    job_id: job.id,
    job_snapshot: job,
  }, { onConflict: 'user_id,job_id' });
  if (error) throw error;
}

export async function removeFavoriteJob(userId, jobId) {
  const client = requireSupabase();
  const { error } = await client
    .from('favorite_jobs')
    .delete()
    .eq('user_id', userId)
    .eq('job_id', jobId);
  if (error) throw error;
}

export async function listSavedPredictions(userId) {
  const client = requireSupabase();
  const { data, error } = await client
    .from('saved_predictions')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(20);
  if (error) throw error;
  return data || [];
}

export async function listFavoriteJobs(userId) {
  const client = requireSupabase();
  const { data, error } = await client
    .from('favorite_jobs')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(50);
  if (error) throw error;
  return data || [];
}
