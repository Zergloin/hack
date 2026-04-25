import { Typography } from 'antd'
import FilterBar from '@/components/dashboard/FilterBar'
import KPICards from '@/components/dashboard/KPICards'
import PopulationChart from '@/components/dashboard/PopulationChart'
import DemographicsChart from '@/components/dashboard/DemographicsChart'
import DriversChart from '@/components/dashboard/DriversChart'
import RankingTables from '@/components/dashboard/RankingTables'

export default function DashboardPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        Мониторинг численности населения
      </Typography.Title>
      <FilterBar />
      <KPICards />
      <PopulationChart />
      <DemographicsChart />
      <DriversChart />
      <RankingTables />
    </div>
  )
}
