import { SaveOutlined, SendOutlined } from '@ant-design/icons';
import { DatePicker, Form, Input, Select, message } from 'antd';
import axios from 'axios';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Card, ErrorState, Loader, PageHeader, Section } from '../../components/design-system';
import { createRequest } from './services/requestService';
import { useReferenceData } from './hooks/useReferenceData';
import type { RequestFormValues, Uuid } from './types/api';
import { getWorkTypeLabel } from './utils';

export function ContractorRequestCreatePage() {
  const [form] = Form.useForm<RequestFormValues>();
  const navigate = useNavigate();
  const referenceData = useReferenceData();
  const selectedCityId = Form.useWatch('city_id', form);
  const selectedFacilityId = Form.useWatch('facility_id', form);
  const selectedPremiseId = Form.useWatch('premise_id', form);
  const selectedWorkTypeIds = Form.useWatch('work_type_ids', form) ?? [];

  const filteredFacilities = useMemo(
    () => referenceData.facilities.filter((facility) => !selectedCityId || facility.city_id === selectedCityId),
    [referenceData.facilities, selectedCityId],
  );
  const filteredPremises = useMemo(
    () => referenceData.premises.filter((premise) => !selectedFacilityId || premise.facility_id === selectedFacilityId),
    [referenceData.premises, selectedFacilityId],
  );
  const premiseRequired = selectedWorkTypeIds.some((id: Uuid) => referenceData.workTypes.find((workType) => workType.id === id)?.requires_premise);

  const selectedPremise = referenceData.premises.find((premise) => premise.id === selectedPremiseId);

  function fillContactsFromPremise(premiseId: Uuid) {
    const premise = referenceData.premises.find((item) => item.id === premiseId);
    if (!premise) {
      return;
    }
    const current = form.getFieldsValue();
    form.setFieldsValue({
      contact_name: current.contact_name || premise.owner_name || undefined,
      contact_email: current.contact_email || premise.owner_email || undefined,
      contact_phone: current.contact_phone || premise.owner_phone || undefined,
    });
  }

  async function submit(values: RequestFormValues) {
    try {
      const created = await createRequest({
        city_id: values.city_id,
        facility_id: values.facility_id,
        premise_id: values.premise_id ?? null,
        title: values.title,
        description: values.description ?? null,
        contact_name: values.contact_name ?? null,
        contact_email: values.contact_email ?? null,
        contact_phone: values.contact_phone ?? null,
        work_type_ids: values.work_type_ids,
      });
      message.success('Заявка создана и отправлена.');
      navigate(`/applications/contractor-requests/${created.id}`);
    } catch (error: unknown) {
      console.error('Failed to create contractor request', error);
      if (axios.isAxiosError(error)) {
        message.error(error.response?.data?.detail ?? 'Backend отклонил заявку.');
        return;
      }
      message.error('Не удалось создать заявку.');
    }
  }

  function saveDraft() {
    const values = form.getFieldsValue();
    localStorage.setItem('contractor-request-draft', JSON.stringify(values));
    message.success('Черновик сохранён локально. Backend DRAFT API пока отсутствует.');
  }

  if (referenceData.isLoading) {
    return <Loader label="Загрузка формы" />;
  }

  if (referenceData.error) {
    return <ErrorState title="Не удалось загрузить справочники" description={referenceData.error} />;
  }

  return (
    <div className="sp-page">
      <PageHeader title="Новая заявка подрядчику" description="Форма использует текущую backend-схему создания заявки." />
      <Section>
        <Card>
          <Form<RequestFormValues> form={form} layout="vertical" onFinish={submit} className="cr-form">
            <Form.Item name="title" label="Заголовок" rules={[{ required: true, message: 'Введите заголовок' }]}>
              <Input />
            </Form.Item>
            <Form.Item name="description" label="Описание">
              <Input.TextArea rows={4} />
            </Form.Item>
            <div className="cr-form-grid">
              <Form.Item name="city_id" label="Город" rules={[{ required: true, message: 'Выберите город' }]}>
                <Select
                  options={referenceData.cities.map((city) => ({ label: city.name, value: city.id }))}
                  onChange={() => form.setFieldsValue({ facility_id: undefined, premise_id: undefined })}
                />
              </Form.Item>
              <Form.Item name="facility_id" label="Объект" rules={[{ required: true, message: 'Выберите объект' }]}>
                <Select
                  options={filteredFacilities.map((facility) => ({ label: facility.name, value: facility.id }))}
                  onChange={() => form.setFieldsValue({ premise_id: undefined })}
                />
              </Form.Item>
            </div>
            <div className="cr-form-grid">
              <Form.Item name="premise_id" label="Помещение" rules={[{ required: premiseRequired, message: 'Помещение обязательно для СКУД' }]}>
                <Select
                  allowClear
                  options={filteredPremises.map((premise) => ({ label: premise.name, value: premise.id }))}
                  onChange={(premiseId?: Uuid) => {
                    if (premiseId) {
                      fillContactsFromPremise(premiseId);
                    }
                  }}
                />
              </Form.Item>
              <Form.Item name="work_type_ids" label="Направления работ" rules={[{ required: true, message: 'Выберите минимум одно направление' }]}>
                <Select
                  mode="multiple"
                  options={referenceData.workTypes.map((workType) => ({ label: getWorkTypeLabel(workType), value: workType.id }))}
                />
              </Form.Item>
            </div>
            <div className="cr-form-grid">
              <Form.Item name="contact_name" label="Контактное лицо">
                <Input placeholder={selectedPremise?.owner_name ?? undefined} />
              </Form.Item>
              <Form.Item name="contact_email" label="Email">
                <Input placeholder={selectedPremise?.owner_email ?? undefined} />
              </Form.Item>
            </div>
            <div className="cr-form-grid">
              <Form.Item name="contact_phone" label="Телефон">
                <Input placeholder={selectedPremise?.owner_phone ?? undefined} />
              </Form.Item>
              <Form.Item name="priority" label="Приоритет">
                <Select
                  disabled
                  placeholder="Не поддерживается backend API"
                  options={[
                    { label: 'Низкий', value: 'low' },
                    { label: 'Обычный', value: 'normal' },
                    { label: 'Высокий', value: 'high' },
                  ]}
                />
              </Form.Item>
            </div>
            <Form.Item name="desired_completion_date" label="Желаемый срок">
              <DatePicker disabled className="cr-date-picker" placeholder="Не поддерживается backend API" />
            </Form.Item>
            <div className="cr-form-actions">
              <Button icon={<SaveOutlined />} onClick={saveDraft}>
                Сохранить черновик
              </Button>
              <Button type="primary" htmlType="submit" icon={<SendOutlined />}>
                Создать и отправить
              </Button>
            </div>
          </Form>
        </Card>
      </Section>
    </div>
  );
}
