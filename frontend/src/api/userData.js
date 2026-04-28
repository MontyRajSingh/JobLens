import { supabase } from '../lib/supabase';

function requireSupabase() {
  if (!supabase) throw new Error('Supabase is not configured.');
  return supabase;
}

function safeName(name) {
  return String(name || 'resume.pdf').replace(/[^a-zA-Z0-9._-]/g, '_');
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

export async function saveOffer(userId, input, result) {
  const client = requireSupabase();
  const { error } = await client.from('saved_offers').insert({
    user_id: userId,
    input,
    result,
  });
  if (error) throw error;
}

export async function uploadResumePdf(userId, file) {
  const client = requireSupabase();
  const path = `${userId}/${crypto.randomUUID()}-${safeName(file.name)}`;
  const { error } = await client.storage.from('resume-pdfs').upload(path, file, {
    contentType: file.type || 'application/pdf',
    upsert: false,
  });
  if (error) throw error;
  return path;
}

export async function saveResume(userId, filePath, extractedData, gapAnalysis, predictionResult) {
  const client = requireSupabase();
  const { error } = await client.from('saved_resumes').insert({
    user_id: userId,
    file_path: filePath,
    extracted_data: extractedData,
    gap_analysis: gapAnalysis,
    prediction_result: predictionResult,
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

export async function listSavedOffers(userId) {
  const client = requireSupabase();
  const { data, error } = await client
    .from('saved_offers')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(20);
  if (error) throw error;
  return data || [];
}

export async function listSavedResumes(userId) {
  const client = requireSupabase();
  const { data, error } = await client
    .from('saved_resumes')
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
