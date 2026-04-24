import api from './client';

export const getMyGaps = async () => {
  const res = await api.get('/users/me/gaps');
  return res.data;
};

export const getMyGapsSummary = async () => {
  const res = await api.get('/users/me/gaps/summary');
  return res.data;
};

