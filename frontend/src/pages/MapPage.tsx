import { Typography } from 'antd'
import PopulationMap from '@/components/map/PopulationMap'

export default function MapPage() {
  return (
    <div style={{ height: 'calc(100vh - 112px)' }}>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        Карта населения России
      </Typography.Title>
      <div style={{ height: 'calc(100% - 48px)' }}>
        <PopulationMap />
      </div>
    </div>
  )
}
