import api from './client';

export const uploadResume = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/resumes/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const startProcessing = async (jobId) => {
  const response = await api.post(`/resumes/${jobId}/process`);
  return response.data;
};

export const pollStatus = async (jobId) => {
  const response = await api.get(`/resumes/${jobId}/status`);
  return response.data;
};

export const getResults = async (jobId) => {
  const response = await api.get(`/resumes/${jobId}/results`);
  return response.data;
};
