import { DeleteOutlined, EditOutlined, SendOutlined } from '@ant-design/icons';
import { Input, Select, Space, Tag, message } from 'antd';
import { useEffect, useState } from 'react';

import { Button, Card, EmptyState, Loader } from '../../../components/design-system';
import { createComment, deleteComment, getComments, updateComment, type CollaborationMode } from '../services/collaborationService';
import type { RequestComment, RequestVisibility, Uuid } from '../types/api';
import { formatDate } from '../utils';

type Props = {
  requestId: Uuid;
  mode: CollaborationMode;
};

export function RequestComments({ requestId, mode }: Props) {
  const [comments, setComments] = useState<RequestComment[]>([]);
  const [body, setBody] = useState('');
  const [visibility, setVisibility] = useState<RequestVisibility>('SHARED');
  const [editingId, setEditingId] = useState<Uuid | null>(null);
  const [editingBody, setEditingBody] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  async function reload() {
    setIsLoading(true);
    try {
      setComments(await getComments(requestId, mode));
    } catch (error) {
      console.error('Failed to load comments', error);
      message.error('Не удалось загрузить комментарии.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, [requestId, mode]);

  async function submit() {
    try {
      await createComment(requestId, mode, body, mode === 'contractor' ? 'SHARED' : visibility);
      setBody('');
      await reload();
    } catch (error) {
      console.error('Failed to create comment', error);
      message.error('Не удалось добавить комментарий.');
    }
  }

  async function saveEdit(commentId: Uuid) {
    try {
      await updateComment(requestId, commentId, mode, editingBody);
      setEditingId(null);
      setEditingBody('');
      await reload();
    } catch (error) {
      console.error('Failed to update comment', error);
      message.error('Не удалось изменить комментарий.');
    }
  }

  async function remove(commentId: Uuid) {
    try {
      await deleteComment(requestId, commentId, mode);
      await reload();
    } catch (error) {
      console.error('Failed to delete comment', error);
      message.error('Не удалось удалить комментарий.');
    }
  }

  if (isLoading) {
    return <Loader label="Загрузка комментариев" />;
  }

  return (
    <Space direction="vertical" className="cr-collaboration-stack">
      <Card>
        <Space direction="vertical" className="cr-collaboration-stack">
          <Input.TextArea rows={3} value={body} onChange={(event) => setBody(event.target.value)} placeholder="Добавить комментарий" maxLength={5000} showCount />
          <div className="cr-collaboration-actions">
            {mode === 'internal' && (
              <Select<RequestVisibility>
                value={visibility}
                className="cr-filter"
                options={[
                  { label: 'Общий', value: 'SHARED' },
                  { label: 'Только для СБ', value: 'INTERNAL' },
                ]}
                onChange={setVisibility}
              />
            )}
            <Button type="primary" icon={<SendOutlined />} onClick={submit} disabled={!body.trim()}>
              Добавить
            </Button>
          </div>
        </Space>
      </Card>
      {comments.length === 0 ? (
        <EmptyState title="Комментариев нет" description="Добавьте первый комментарий по заявке." />
      ) : (
        comments.map((comment) => (
          <Card key={comment.id}>
            <Space direction="vertical" className="cr-collaboration-stack">
              <div className="cr-comment-meta">
                <Space wrap>
                  <Tag>{comment.author_type}</Tag>
                  <Tag color={comment.visibility === 'INTERNAL' ? 'orange' : 'blue'}>{comment.visibility === 'INTERNAL' ? 'Только для СБ' : 'Общий'}</Tag>
                  {comment.is_edited && <Tag>изменен</Tag>}
                  {comment.is_deleted && <Tag color="red">удален</Tag>}
                </Space>
                <span>{formatDate(comment.updated_at || comment.created_at)}</span>
              </div>
              {editingId === comment.id ? (
                <Space direction="vertical" className="cr-collaboration-stack">
                  <Input.TextArea rows={3} value={editingBody} onChange={(event) => setEditingBody(event.target.value)} maxLength={5000} showCount />
                  <Space>
                    <Button type="primary" onClick={() => saveEdit(comment.id)} disabled={!editingBody.trim()}>
                      Сохранить
                    </Button>
                    <Button onClick={() => setEditingId(null)}>Отмена</Button>
                  </Space>
                </Space>
              ) : (
                <p className="cr-comment-body">{comment.body}</p>
              )}
              {!comment.is_deleted && editingId !== comment.id && (
                <Space>
                  <Button icon={<EditOutlined />} onClick={() => { setEditingId(comment.id); setEditingBody(comment.body); }}>
                    Изменить
                  </Button>
                  <Button icon={<DeleteOutlined />} danger onClick={() => remove(comment.id)}>
                    Удалить
                  </Button>
                </Space>
              )}
            </Space>
          </Card>
        ))
      )}
    </Space>
  );
}
