import { useState } from 'react'
import { Card, Select, Button, Row, Col, Space, Divider, Empty, Spin, message } from 'antd'
import { FileTextOutlined, FilePdfOutlined, FileWordOutlined } from '@ant-design/icons'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchRegions, fetchMunicipalitiesByRegion } from '@/api/population'
import { generateReport, exportReport, type ReportOut } from '@/api/reports'

export default function ReportView() {
  const [regionId, setRegionId] = useState<number | null>(null)
  const [municipalityId, setMunicipalityId] = useState<number | null>(null)
  const [reportType, setReportType] = useState('comprehensive')
  const [report, setReport] = useState<ReportOut | null>(null)

  const { data: regions = [] } = useQuery({
    queryKey: ['regions'],
    queryFn: fetchRegions,
  })

  const { data: municipalities = [] } = useQuery({
    queryKey: ['municipalities', regionId],
    queryFn: () => fetchMunicipalitiesByRegion(regionId!),
    enabled: !!regionId,
  })

  const genMutation = useMutation({
    mutationFn: () =>
      generateReport({
        report_type: reportType,
        region_id: regionId,
        municipality_id: municipalityId,
      }),
    onSuccess: (data) => {
      setReport(data)
      message.success('Отчёт сгенерирован')
    },
    onError: () => message.error('Ошибка генерации отчёта'),
  })

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!report) return
    try {
      await exportReport(report.id, format)
      message.success(`Файл ${format.toUpperCase()} скачан`)
    } catch {
      message.error('Ошибка экспорта')
    }
  }

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col xs={24} sm={6}>
            <Select
              value={reportType}
              onChange={setReportType}
              style={{ width: '100%' }}
              options={[
                { value: 'comprehensive', label: 'Комплексный' },
                { value: 'monitoring', label: 'Мониторинг' },
                { value: 'forecast', label: 'Прогнозный' },
              ]}
            />
          </Col>
          <Col xs={24} sm={6}>
            <Select
              placeholder="Регион"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
              value={regionId}
              onChange={(val) => {
                setRegionId(val ?? null)
                setMunicipalityId(null)
              }}
              options={regions.map((r) => ({ value: r.id, label: r.name }))}
            />
          </Col>
          <Col xs={24} sm={6}>
            <Select
              placeholder="Муниципалитет"
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: '100%' }}
              value={municipalityId}
              onChange={(val) => setMunicipalityId(val ?? null)}
              disabled={!regionId}
              options={municipalities.map((m) => ({ value: m.id, label: m.name }))}
            />
          </Col>
          <Col xs={24} sm={6}>
            <Button
              type="primary"
              icon={<FileTextOutlined />}
              onClick={() => genMutation.mutate()}
              loading={genMutation.isPending}
              block
            >
              Сгенерировать
            </Button>
          </Col>
        </Row>
      </Card>

      {genMutation.isPending && (
        <Card>
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" tip="Генерация отчёта..." />
          </div>
        </Card>
      )}

      {report && !genMutation.isPending && (
        <Card
          title={report.title}
          extra={
            <Space>
              <Button
                icon={<FilePdfOutlined />}
                onClick={() => handleExport('pdf')}
              >
                PDF
              </Button>
              <Button
                icon={<FileWordOutlined />}
                onClick={() => handleExport('docx')}
              >
                Word
              </Button>
            </Space>
          }
        >
          <div
            className="report-content"
            dangerouslySetInnerHTML={{
              __html: report.content_html || report.content_markdown,
            }}
            style={{ lineHeight: 1.8, fontSize: 14 }}
          />
          <Divider />
          <div style={{ color: '#718096', fontSize: 12 }}>
            Сгенерировано: {new Date(report.created_at).toLocaleString('ru-RU')}
          </div>
        </Card>
      )}

      {!report && !genMutation.isPending && (
        <Card>
          <Empty description="Выберите параметры и нажмите 'Сгенерировать'" />
        </Card>
      )}
    </div>
  )
}
