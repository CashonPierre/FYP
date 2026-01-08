// src/routes/backtest/input/+page.server.ts
import { redirect } from '@sveltejs/kit';

export const actions = {
  default: async ({ request }) => {
    const formData = await request.formData();
    const strategyCode = formData.get('strategyCode')?.toString() || '';
    const initialCapital = Number(formData.get('initialCapital')) || 10000;

    // 🚧 TEMP: Simulate job_id (replace with FastAPI call later)
    const job_id = 'sim_' + Date.now();

    console.log('Submitting backtest:', { strategyCode, initialCapital, job_id });

    // ✅ Redirect to results
    throw redirect(303, `/backtest/results/${job_id}`);
  }
};