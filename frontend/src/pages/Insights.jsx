import { useState, useEffect } from 'react';
import { BarChart3 } from 'lucide-react';
import {
  getSalaryByCity,
  getTopSkills,
  getRemoteVsOnsite,
  getSalaryBySeniority,
  searchJobs,
} from '../api/client';
import {
  SalaryByCityChart,
  TopSkillsChart,
  RemoteVsOnsiteChart,
  SeniorityLadderChart,
  SalaryDistributionChart,
} from '../components/Charts';

export default function Insights() {
  const [cityData, setCityData] = useState({ data: null, loading: true, error: null });
  const [skillsData, setSkillsData] = useState({ data: null, loading: true, error: null });
  const [remoteData, setRemoteData] = useState({ data: null, loading: true, error: null });
  const [seniorityData, setSeniorityData] = useState({ data: null, loading: true, error: null });
  const [jobsData, setJobsData] = useState({ data: null, loading: true, error: null });

  const loadCity = async () => {
    setCityData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getSalaryByCity();
      setCityData({ data, loading: false, error: null });
    } catch (e) {
      setCityData({ data: null, loading: false, error: e.message });
    }
  };

  const loadSkills = async () => {
    setSkillsData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getTopSkills();
      setSkillsData({ data, loading: false, error: null });
    } catch (e) {
      setSkillsData({ data: null, loading: false, error: e.message });
    }
  };

  const loadRemote = async () => {
    setRemoteData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getRemoteVsOnsite();
      setRemoteData({ data, loading: false, error: null });
    } catch (e) {
      setRemoteData({ data: null, loading: false, error: e.message });
    }
  };

  const loadSeniority = async () => {
    setSeniorityData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const data = await getSalaryBySeniority();
      setSeniorityData({ data, loading: false, error: null });
    } catch (e) {
      setSeniorityData({ data: null, loading: false, error: e.message });
    }
  };

  const loadJobs = async () => {
    setJobsData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const data = await searchJobs({ page_size: 100 });
      setJobsData({ data: data.results, loading: false, error: null });
    } catch (e) {
      setJobsData({ data: null, loading: false, error: e.message });
    }
  };

  useEffect(() => {
    loadCity();
    loadSkills();
    loadRemote();
    loadSeniority();
    loadJobs();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
        <BarChart3 className="text-brand-400" size={28} /> Market Insights
      </h1>
      <p className="text-slate-400 mb-8">Real-time analytics from scraped job market data</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Salary by City */}
        <div className="lg:col-span-2">
          <SalaryByCityChart
            data={cityData.data}
            loading={cityData.loading}
            error={cityData.error}
            onRetry={loadCity}
          />
        </div>

        {/* Chart 2: Top Skills */}
        <TopSkillsChart
          data={skillsData.data}
          loading={skillsData.loading}
          error={skillsData.error}
          onRetry={loadSkills}
        />

        {/* Chart 3: Remote vs Onsite */}
        <RemoteVsOnsiteChart
          data={remoteData.data}
          loading={remoteData.loading}
          error={remoteData.error}
          onRetry={loadRemote}
        />

        {/* Chart 4: Seniority Ladder */}
        <SeniorityLadderChart
          data={seniorityData.data}
          loading={seniorityData.loading}
          error={seniorityData.error}
          onRetry={loadSeniority}
        />

        {/* Chart 5: Salary Distribution */}
        <SalaryDistributionChart
          jobs={jobsData.data}
          loading={jobsData.loading}
          error={jobsData.error}
          onRetry={loadJobs}
        />
      </div>
    </div>
  );
}
