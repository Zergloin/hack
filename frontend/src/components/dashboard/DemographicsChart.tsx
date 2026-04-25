import { useState } from 'react'
import { Card, Empty, Segmented, Space, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { fetchDemographicsTimeseries } from '@/api/population'
import { useFilterStore } from '@/store/useFilterStore'

export default function DemographicsChart() {
  const { municipalityId, regionId, yearFrom, yearTo } = useFilterStore()
  const [mode, setMode] = useState<'rates' | 'absolute'>('rates')

  const { data: timeseries = [], isLoading } = useQuery({
    queryKey: ['demographicsTimeseries', municipalityId, regionId, yearFrom, yearTo],
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
        formatter: (value: number) => {
          if (mode === 'rates') {
            return `${value.toFixed(1)}‰`
          }
          return value >= 1_000 || value <= -1_000
            ? `${value > 0 ? '+' : ''}${(value / 1_000).toFixed(0)}К`
            : `${value > 0 ? '+' : ''}${value}`
        },
      },
    },
    series: mode === 'rates'
      ? [
          {
            name: 'Рождаемость',
            type: 'line',
            data: series?.data.map((point) => point.birth_rate) ?? [],
            smooth: true,
            lineStyle: { width: 2, color: '#389e0d' },
            itemStyle: { color: '#389e0d' },
          },
          {
            name: 'Смертность',
            type: 'line',
            data: series?.data.map((point) => point.death_rate) ?? [],
            smooth: true,
            lineStyle: { width: 2, color: '#cf1322' },
            itemStyle: { color: '#cf1322' },
          },
          {
            name: 'Ест. прирост',
            type: 'bar',
            data: series?.data.map((point) => point.natural_growth_rate) ?? [],
            itemStyle: {
              color: (params: any) => (params.value >= 0 ? '#52c41a' : '#ff4d4f'),
            },
          },
          {
            name: 'Миграция',
            type: 'bar',
            data: series?.data.map((point) => point.net_migration_rate) ?? [],
            itemStyle: {
              color: (params: any) => (params.value >= 0 ? '#722ed1' : '#fa8c16'),
            },
          },
        ]
      : [
          {
            name: 'Рождения',
            type: 'bar',
            data: series?.data.map((point) => point.births) ?? [],
            itemStyle: { color: '#73d13d' },
          },
          {
            name: 'Смерти',
            type: 'bar',
            data: series?.data.map((point) => point.deaths) ?? [],
            itemStyle: { color: '#ff7875' },
          },
          {
            name: 'Ест. прирост',
            type: 'line',
            data: series?.data.map((point) => point.natural_growth) ?? [],
            smooth: true,
            lineStyle: { width: 3, color: '#237804' },
            itemStyle: { color: '#237804' },
          },
          {
            name: 'Чистая миграция',
            type: 'line',
            data: series?.data.map((point) => point.net_migration) ?? [],
            smooth: true,
            lineStyle: { width: 3, color: '#531dab' },
            itemStyle: { color: '#531dab' },
          },
        ],
    animationDuration: 800,
  }

  return (
    <Card
      title="Демографические показатели"
      loading={isLoading}
      style={{ marginBottom: 16 }}
      extra={(
        <Space size="middle">
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {series?.municipality_name || 'Нет данных'}
          </Typography.Text>
          <Segmented
            size="small"
            options={[
              { label: 'Коэффициенты', value: 'rates' },
              { label: 'Абсолютные', value: 'absolute' },
            ]}
            value={mode}
            onChange={(value) => setMode(value as 'rates' | 'absolute')}
          />
        </Space>
      )}
    >
      {series ? (
        <ReactECharts option={option} style={{ height: 340 }} />
      ) : (
        <Empty description="Демографические показатели не найдены" />
      )}
    </Card>
  )
}
