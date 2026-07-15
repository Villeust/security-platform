import { Space } from 'antd';

import { Card } from '../../../components/design-system';
import type { CollaborationMode } from '../services/collaborationService';
import type { Contractor, RequestAssignment, Uuid, WorkType } from '../types/api';
import { contractorName, getWorkTypeLabel } from '../utils';
import { RequestStatusBadge } from './RequestStatusBadge';
import { RequestAttachments } from './RequestAttachments';

type Props = {
  requestId: Uuid;
  assignments: RequestAssignment[];
  contractors: Contractor[];
  workTypes: WorkType[];
  mode: CollaborationMode;
};

export function AssignmentWorkResults({ requestId, assignments, contractors, workTypes, mode }: Props) {
  return (
    <Space direction="vertical" className="cr-collaboration-stack">
      {assignments.map((assignment) => (
        <Card key={assignment.id}>
          <Space direction="vertical" className="cr-collaboration-stack">
            <Space wrap>
              <strong>{contractorName(assignment.contractor_id, contractors)}</strong>
              <span>{getWorkTypeLabel(workTypes.find((workType) => workType.id === assignment.work_type_id))}</span>
              <RequestStatusBadge status={assignment.status} />
            </Space>
            <RequestAttachments requestId={requestId} mode={mode} assignmentId={assignment.id} category="WORK_RESULT" />
          </Space>
        </Card>
      ))}
    </Space>
  );
}
