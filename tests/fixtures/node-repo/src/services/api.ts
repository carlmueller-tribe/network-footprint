import axios from 'axios';

export async function getUser(id: string) {
  return axios.get(`/api/users/${id}`);
}

export async function createItem(data: object) {
  return axios.post('/api/items', data);
}
