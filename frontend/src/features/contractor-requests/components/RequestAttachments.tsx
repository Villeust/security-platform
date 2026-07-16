import { DeleteOutlined, DownloadOutlined, InboxOutlined } from '@ant-design/icons';
import { Select, Space, Table, Upload, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';

import { Button, EmptyState, Loader } from '../../../components/design-system';
import { notifyApiError } from '../../../lib/toast';
import { attachmentDownloadUrl, deleteAttachment, getAttachments, uploadAttachment, type CollaborationMode } from '../services/collaborationService';
import type { RequestAttachment, RequestAttachmentCategory, RequestVisibility, Uuid } from '../types/api';
import { formatDate } from '../utils';

type Props = {
  requestId: Uuid;
  mode: CollaborationMode;
  assignmentId?: Uuid | null;
  category?: RequestAttachmentCategory;
};

const categories: RequestAttachmentCategory[] = ['REQUEST_FILE', 'WORK_RESULT', 'ACT', 'PHOTO', 'DOCUMENT', 'OTHER'];

export function RequestAttachments({ requestId, mode, assignmentId = null, category }: Props) {
  const [attachments, setAttachments] = useState<RequestAttachment[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<RequestAttachmentCategory>(category ?? 'REQUEST_FILE');
  const [visibility, setVisibility] = useState<RequestVisibility>('SHARED');
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);

  async function reload() {
    setIsLoading(true);
    try {
      const data = await getAttachments(requestId, mode);
      setAttachments(category ? data.filter((attachment) => attachment.category === category && attachment.assignment_id === assignmentId) : data);
    } catch (error) {
      console.error('Failed to load attachments', error);
      notifyApiError(error, 'Не удалось загрузить вложения.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, [requestId, mode, assignmentId, category]);

  async function upload(file: File) {
    setIsUploading(true);
    try {
      await uploadAttachment(requestId, mode, file, selectedCategory, mode === 'contractor' ? 'SHARED' : visibility, assignmentId);
      message.success('Файл загружен.');
      await reload();
    } catch (error: unknown) {
      console.error('Failed to upload attachment', error);
      notifyApiError(error, 'Не удалось загрузить файл.');
    } finally {
      setIsUploading(false);
    }
  }

  async function remove(attachmentId: Uuid) {
    try {
      await deleteAttachment(requestId, attachmentId, mode);
      await reload();
    } catch (error) {
      console.error('Failed to delete attachment', error);
      notifyApiError(error, 'Не удалось удалить вложение.');
    }
  }

  const columns: ColumnsType<RequestAttachment> = [
    { title: 'Файл', dataIndex: 'original_filename', key: 'original_filename' },
    { title: 'Категория', dataIndex: 'category', key: 'category' },
    { title: 'Размер', dataIndex: 'size_bytes', key: 'size_bytes', render: (value: number) => `${Math.round(value / 1024)} KB` },
    { title: 'Дата', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDate(value) },
    {
      title: 'Действия',
      key: 'actions',
      render: (_value, attachment) => (
        <Space>
          <Button icon={<DownloadOutlined />} href={attachmentDownloadUrl(requestId, attachment.id, mode)}>
            Скачать
          </Button>
          <Button icon={<DeleteOutlined />} danger onClick={() => remove(attachment.id)}>
            Удалить
          </Button>
        </Space>
      ),
    },
  ];

  if (isLoading) {
    return <Loader label="Загрузка вложений" />;
  }

  return (
    <Space direction="vertical" className="cr-collaboration-stack">
      <div className="cr-collaboration-actions">
        {!category && (
          <Select<RequestAttachmentCategory>
            value={selectedCategory}
            className="cr-filter"
            options={categories.map((item) => ({ label: item, value: item }))}
            onChange={setSelectedCategory}
          />
        )}
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
      </div>
      <Upload.Dragger
        multiple
        showUploadList={false}
        disabled={isUploading}
        beforeUpload={(file) => {
          void upload(file);
          return Upload.LIST_IGNORE;
        }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">Перетащите файл сюда или выберите на диске</p>
      </Upload.Dragger>
      {attachments.length === 0 ? <EmptyState title="Вложений нет" description="Загрузите первый файл по заявке." /> : <Table<RequestAttachment> rowKey="id" columns={columns} dataSource={attachments} pagination={false} />}
    </Space>
  );
}
