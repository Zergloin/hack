import { Card, Empty } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchDemographicsTimeseries } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'

export default function DemographicsChart() {
  const { municipalityId, yearFrom, yearTo } = useFilterStore()

  const { data: timeseries = [], isLoading } = useQuery({
    queryKey: ['demographicsTimeseries', municipalityId, yearFrom, yearTo],
    queryFn: () =>
      fetchDemographicsTimeseries({ municipality_id: [municipalityId!], year_from: yearFrom, year_to: yearTo }),
    enabled: !!municipalityId,
  })

  if (!municipalityId) {
    return (
      <Card title="Демографические показатели" style={{ marginBottom: 16 }}>
        <Empty description="Выберите муниципалитет" />
      </Card>
    )
  }

  const series = timeseries[0]
  const years = series?.data.map((d) => d.year) ?? []

  const option = {
    tooltip: { trigger: 'axis' as const },
    legend: { top: 0 },
    grid: { left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category' as const, data: years },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (val: number) => `${val.toFixed(1)}`,
      },
    },
    series: [
      {
        name: 'Рождаемость',
        type: 'line',
        data: series?.data.map((d) => d.birth_rate) ?? [],
        smooth: true,
        lineStyle: { width: 2, color: '#38a169' },
        itemStyle: { color: '#38a169' },
      },
      {
        name: 'Смертность',
        type: 'line',
        data: series?.data.map((d) => d.death_rate) ?? [],
        smooth: true,
        lineStyle: { width: 2, color: '#e53e3e' },
        itemStyle: { color: '#e53e3e' },
      },
      {
        name: 'Ест. прирост',
        type: 'bar',
        data: series?.data.map((d) => d.natural_growth_rate) ?? [],
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? '#38a169' : '#e53e3e'),
        },
      },
      {
        name: 'Миграция',
        type: 'bar',
        data: series?.data.map((d) => d.net_migration_rate) ?? [],
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? '#805ad5' : '#d69e2e'),
        },
      },
    ],
    animationDuration: 800,
  }

  return (
    <Card title="Демографические показатели" loading={isLoading} style={{ marginBottom: 16 }}>
      <ReactECharts option={option} style={{ height: 300 }} />
    </Card>
  )
}
