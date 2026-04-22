import { Typography } from 'antd'
import ForecastView from '@/components/forecast/ForecastView'

export default function ForecastPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        Прогнозирование численности населения
      </Typography.Title>
      <ForecastView />
    </div>
  )
}
