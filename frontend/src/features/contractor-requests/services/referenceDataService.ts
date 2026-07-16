import { api } from '../../../services/api';
import type { City, Contractor, Facility, Premise, WorkType } from '../types/api';

export async function getCities(signal?: AbortSignal) {
  const response = await api.get<City[]>('/api/v1/cities', { params: { limit: 100, is_active: true }, signal });
  return response.data;
}

export async function getFacilities(signal?: AbortSignal) {
  const response = await api.get<Facility[]>('/api/v1/facilities', { params: { limit: 100, is_active: true }, signal });
  return response.data;
}

export async function getPremises(signal?: AbortSignal) {
  const response = await api.get<Premise[]>('/api/v1/premises', { params: { limit: 100, is_active: true }, signal });
  return response.data;
}

export async function getWorkTypes(signal?: AbortSignal) {
  const response = await api.get<WorkType[]>('/api/v1/work-types', { params: { limit: 100, is_active: true }, signal });
  return response.data;
}

export async function getContractors(signal?: AbortSignal) {
  const response = await api.get<Contractor[]>('/api/v1/contractors', { params: { limit: 100, is_active: true }, signal });
  return response.data;
}
