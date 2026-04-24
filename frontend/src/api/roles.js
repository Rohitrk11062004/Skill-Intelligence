import api from './client';

export const listRoles = async () => {
  const res = await api.get('/roles');
  return res.data;
};

export const getRoleSkills = async (roleId) => {
  const res = await api.get(`/roles/${roleId}/skills`);
  return res.data;
};

export const getMyTargetRole = async () => {
  const res = await api.get('/users/me/target-role');
  return res.data;
};

export const setMyTargetRole = async ({ roleId, roleName } = {}) => {
  const payload = {};
  if (roleId) payload.role_id = roleId;
  if (roleName) payload.role_name = roleName;
  const res = await api.post('/users/me/target-role', payload);
  return res.data;
};

export const ingestJd = async ({ file, roleName, department, seniorityLevel } = {}) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('role_name', roleName);
  if (department) fd.append('department', department);
  if (seniorityLevel) fd.append('seniority_level', seniorityLevel);
  const res = await api.post('/roles/ingest-jd', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
};

