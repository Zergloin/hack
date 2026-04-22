import { Typography } from 'antd'
import ReportView from '@/components/reports/ReportView'

export default function ReportsPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        Аналитические отчёты
      </Typography.Title>
      <ReportView />
    </div>
  )
}
