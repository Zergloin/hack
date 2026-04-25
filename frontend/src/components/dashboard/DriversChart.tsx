import { Card, Empty, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchDemographicsTimeseries } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'

export default function DriversChart() {
  const { municipalityId, regionId, yearFrom, yearTo } = useFilterStore()

  const { data: timeseries = [], isLoading } = useQuery({
    queryKey: ['driversTimeseries', municipalityId, regionId, yearFrom, yearTo],
    queryFn: () =>
      fetchDemographicsTimeseries({
        municipality_id: municipalityId ? [municipalityId] : [],
        region_id: municipalityId ? undefined : regionId ?? undefined,
        year_from: yearFrom,
        year_to: yearTo,
      }),
  })

  const series = timeseries[0]
  const years = series?.data.map((point) => point.year) ?? []
  const totalEffect = series?.data.map((point) => (point.natural_growth ?? 0) + (point.net_migration ?? 0)) ?? []

  const option = {
    tooltip: { trigger: 'axis' as const },
    legend: { top: 0 },
    grid: { left: 60, right: 30, top: 50, bottom: 60 },
    dataZoom: [
      { type: 'inside' as const, start: 0, end: 100 },
      { type: 'slider' as const, bottom: 10, height: 18 },
    ],
    xAxis: { type: 'category' as const, data: years },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (value: number) =>
          value >= 1_000 || value <= -1_000
            ? `${value > 0 ? '+' : ''}${(value / 1_000).toFixed(0)}К`
            : `${value > 0 ? '+' : ''}${value}`,
      },
    },
    series: [
      {
        name: 'Естественный прирост',
        type: 'bar',
        data: series?.data.map((point) => point.natural_growth) ?? [],
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? '#52c41a' : '#ff4d4f'),
        },
      },
      {
        name: 'Чистая миграция',
        type: 'bar',
        data: series?.data.map((point) => point.net_migration) ?? [],
        itemStyle: {
          color: (params: any) => (params.value >= 0 ? '#722ed1' : '#fa8c16'),
        },
      },
      {
        name: 'Суммарный эффект',
        type: 'line',
        data: totalEffect,
        smooth: true,
        lineStyle: { width: 3, color: '#1f1f1f' },
        itemStyle: { color: '#1f1f1f' },
      },
    ],
    animationDuration: 800,
  }

  return (
    <Card
      title="Факторы изменения населения"
      loading={isLoading}
      style={{ marginBottom: 16 }}
      extra={(
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {series?.municipality_name || 'Нет данных'}
        </Typography.Text>
      )}
    >
      {series ? (
        <ReactECharts option={option} style={{ height: 320 }} />
      ) : (
        <Empty description="Факторы изменения не найдены" />
      )}
    </Card>
  )
}
