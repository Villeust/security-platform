import { StatusBadge } from '../../../components/design-system';
import type { AssignmentStatus, RequestStatus } from '../types/api';

type Props = {
  status: RequestStatus | AssignmentStatus;
};

export function RequestStatusBadge({ status }: Props) {
  if (status === 'ASSIGNED' || status === 'ACCEPTED' || status === 'IN_PROGRESS' || status === 'PARTIALLY_ASSIGNED') {
    return <StatusBadge label={status} tone="processing" />;
  }
  if (status === 'COMPLETED' || status === 'CLOSED') {
    return <StatusBadge label={status} tone="success" />;
  }
  if (status === 'CANCELLED') {
    return <StatusBadge label={status} tone="error" />;
  }
  return <StatusBadge label={status} tone="warning" />;
}
