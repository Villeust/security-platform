import { api } from '../../../services/api';
import type { RequestAttachment, RequestAttachmentCategory, RequestComment, RequestVisibility, Uuid } from '../types/api';

export type CollaborationMode = 'internal' | 'contractor';

function prefix(mode: CollaborationMode) {
  return mode === 'contractor' ? '/api/v1/contractor' : '/api/v1';
}

export async function getComments(requestId: Uuid, mode: CollaborationMode) {
  const response = await api.get<RequestComment[]>(`${prefix(mode)}/requests/${requestId}/comments`);
  return response.data;
}

export async function createComment(requestId: Uuid, mode: CollaborationMode, body: string, visibility: RequestVisibility) {
  const response = await api.post<RequestComment>(`${prefix(mode)}/requests/${requestId}/comments`, { body, visibility });
  return response.data;
}

export async function updateComment(requestId: Uuid, commentId: Uuid, mode: CollaborationMode, body: string) {
  const response = await api.patch<RequestComment>(`${prefix(mode)}/requests/${requestId}/comments/${commentId}`, { body });
  return response.data;
}

export async function deleteComment(requestId: Uuid, commentId: Uuid, mode: CollaborationMode) {
  const response = await api.delete<RequestComment>(`${prefix(mode)}/requests/${requestId}/comments/${commentId}`);
  return response.data;
}

export async function getAttachments(requestId: Uuid, mode: CollaborationMode) {
  const response = await api.get<RequestAttachment[]>(`${prefix(mode)}/requests/${requestId}/attachments`);
  return response.data;
}

export async function uploadAttachment(
  requestId: Uuid,
  mode: CollaborationMode,
  file: File,
  category: RequestAttachmentCategory,
  visibility: RequestVisibility,
  assignmentId?: Uuid | null,
  commentId?: Uuid | null,
) {
  const form = new FormData();
  form.append('file', file);
  form.append('category', category);
  form.append('visibility', visibility);
  if (assignmentId) {
    form.append('assignment_id', assignmentId);
  }
  if (commentId) {
    form.append('comment_id', commentId);
  }
  const response = await api.post<RequestAttachment>(`${prefix(mode)}/requests/${requestId}/attachments`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function deleteAttachment(requestId: Uuid, attachmentId: Uuid, mode: CollaborationMode) {
  const response = await api.delete<RequestAttachment>(`${prefix(mode)}/requests/${requestId}/attachments/${attachmentId}`);
  return response.data;
}

export function attachmentDownloadUrl(requestId: Uuid, attachmentId: Uuid, mode: CollaborationMode) {
  return `${api.defaults.baseURL}${prefix(mode)}/requests/${requestId}/attachments/${attachmentId}/download`;
}
