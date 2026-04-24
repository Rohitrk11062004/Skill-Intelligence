import api from './client';

export const getMyAssessmentsSummary = async () => {
  const response = await api.get('/assessments/summary');
  return response.data;
};

export const getWeekAssessment = async (planId, weekNumber) => {
  const response = await api.get(`/assessments/weeks/${planId}/${weekNumber}`);
  return response.data;
};

export const submitWeekAssessment = async (planId, weekNumber, answers) => {
  const response = await api.post(`/assessments/weeks/${planId}/${weekNumber}/submit`, { answers });
  return response.data;
};

export const getWeekAssessmentHistory = async (planId, weekNumber) => {
  const response = await api.get(`/assessments/weeks/${planId}/${weekNumber}/history`);
  return response.data;
};

