#include "mainwindow.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonValue>
#include <QDateTime>
#include <QFont>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , m_networkManager(new QNetworkAccessManager(this))
    , m_timer(new QTimer(this))
    , m_serverUrl("http://localhost:5000/api/data")
{
    setWindowTitle("Weather Station Client");
    setMinimumSize(800, 600);
    
    connect(m_networkManager, &QNetworkAccessManager::finished,
            this, &MainWindow::onDataReceived);
    
    connect(m_timer, &QTimer::timeout, this, &MainWindow::requestData);
    m_timer->start(2000); // Update every 2 seconds
    
    setupUI();
    requestData();
}

void MainWindow::setupUI()
{
    QWidget *centralWidget = new QWidget(this);
    QVBoxLayout *mainLayout = new QVBoxLayout(centralWidget);
    
    // Title
    QLabel *titleLabel = new QLabel("🌤️ Weather Station Monitor", this);
    QFont titleFont = titleLabel->font();
    titleFont.setPointSize(20);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);
    titleLabel->setAlignment(Qt::AlignCenter);
    mainLayout->addWidget(titleLabel);
    
    // Last update label
    m_lastUpdateLabel = new QLabel("Last update: -", this);
    m_lastUpdateLabel->setAlignment(Qt::AlignRight);
    mainLayout->addWidget(m_lastUpdateLabel);
    
    // Arduino sensors group
    QGroupBox *arduinoGroup = new QGroupBox("📡 Arduino Sensors", this);
    QVBoxLayout *arduinoLayout = new QVBoxLayout(arduinoGroup);
    m_arduinoLabel = new QLabel("Loading...", this);
    m_arduinoLabel->setWordWrap(true);
    arduinoLayout->addWidget(m_arduinoLabel);
    mainLayout->addWidget(arduinoGroup);
    
    // Elbear sensors group
    QGroupBox *elbearGroup = new QGroupBox("🤖 Elbear Sensors", this);
    QVBoxLayout *elbearLayout = new QVBoxLayout(elbearGroup);
    m_elbearLabel = new QLabel("Loading...", this);
    m_elbearLabel->setWordWrap(true);
    elbearLayout->addWidget(m_elbearLabel);
    mainLayout->addWidget(elbearGroup);
    
    setCentralWidget(centralWidget);
}

void MainWindow::requestData()
{
    QNetworkRequest request{QUrl(m_serverUrl)};
    m_networkManager->get(request);
}

void MainWindow::onDataReceived(QNetworkReply *reply)
{
    if (reply->error() == QNetworkReply::NoError) {
        QByteArray responseData = reply->readAll();
        QJsonDocument jsonDoc = QJsonDocument::fromJson(responseData);
        QJsonObject jsonObj = jsonDoc.object();
        
        updateDisplay(jsonObj);
    } else {
        m_arduinoLabel->setText("Error: " + reply->errorString());
        m_elbearLabel->setText("Check server connection");
    }
    
    reply->deleteLater();
}

void MainWindow::updateDisplay(const QJsonObject &data)
{
    QJsonObject arduino = data["arduino"].toObject();
    QJsonObject elbear = data["elbear"].toObject();
    QString lastUpdate = data["last_update"].toString();
    
    // Arduino
    QString arduinoText = QString(
        "Temperature: %1 °C\n"
        "Humidity: %2 %\n"
        "Pressure: %3 mmHg\n"
        "Timestamp: %4"
    ).arg(arduino["temp"].isNull() ? "N/A" : QString::number(arduino["temp"].toDouble(), 'f', 1))
     .arg(arduino["humid"].isNull() ? "N/A" : QString::number(arduino["humid"].toDouble(), 'f', 1))
     .arg(arduino["press"].isNull() ? "N/A" : QString::number(arduino["press"].toDouble(), 'f', 1))
     .arg(arduino["timestamp"].toString());
    
    m_arduinoLabel->setText(arduinoText);
    
    // Elbear
    QString elbearText = QString(
        "=== Environment ===\n"
        "THP80 Temp: %1 °C\n"
        "THP80 Hum: %2 %\n"
        "THP80 Press: %3 mmHg\n"
        "L75 Light: %4 lux\n"
        "FR403 Flame: %5\n"
        "\n"
        "=== Color (CLM60) ===\n"
        "R: %6  G: %7  B: %8\n"
        "Clear: %9  Prox: %10\n"
        "\n"
        "=== Motion (A6) ===\n"
        "Accel: %11, %12, %13 m/s²\n"
        "Gyro: %14, %15, %16 °/s\n"
        "\n"
        "=== Air (CO30) ===\n"
        "eCO2: %17 ppm\n"
        "TVOC: %18 ppb\n"
        "\n"
        "=== Distance (D20) ===\n"
        "Distance: %19 mm\n"
        "\n"
        "Timestamp: %20"
    ).arg(elbear["THP80_temp"].isNull() ? "N/A" : QString::number(elbear["THP80_temp"].toDouble(), 'f', 1))
     .arg(elbear["THP80_hum"].isNull() ? "N/A" : QString::number(elbear["THP80_hum"].toDouble(), 'f', 1))
     .arg(elbear["THP80_press"].isNull() ? "N/A" : QString::number(elbear["THP80_press"].toDouble(), 'f', 1))
     .arg(elbear["L75_lux"].isNull() ? "N/A" : QString::number(elbear["L75_lux"].toDouble(), 'f', 1))
     .arg(elbear["FR403_flame"].isNull() ? "N/A" : elbear["FR403_flame"].toString())
     .arg(elbear["CLM60_red"].isNull() ? "N/A" : QString::number(elbear["CLM60_red"].toInt()))
     .arg(elbear["CLM60_green"].isNull() ? "N/A" : QString::number(elbear["CLM60_green"].toInt()))
     .arg(elbear["CLM60_blue"].isNull() ? "N/A" : QString::number(elbear["CLM60_blue"].toInt()))
     .arg(elbear["CLM60_clear"].isNull() ? "N/A" : QString::number(elbear["CLM60_clear"].toInt()))
     .arg(elbear["CLM60_proximity"].isNull() ? "N/A" : QString::number(elbear["CLM60_proximity"].toInt()))
     .arg(elbear["A6_accel_x"].isNull() ? "N/A" : QString::number(elbear["A6_accel_x"].toDouble(), 'f', 2))
     .arg(elbear["A6_accel_y"].isNull() ? "N/A" : QString::number(elbear["A6_accel_y"].toDouble(), 'f', 2))
     .arg(elbear["A6_accel_z"].isNull() ? "N/A" : QString::number(elbear["A6_accel_z"].toDouble(), 'f', 2))
     .arg(elbear["A6_gyro_x"].isNull() ? "N/A" : QString::number(elbear["A6_gyro_x"].toDouble(), 'f', 2))
     .arg(elbear["A6_gyro_y"].isNull() ? "N/A" : QString::number(elbear["A6_gyro_y"].toDouble(), 'f', 2))
     .arg(elbear["A6_gyro_z"].isNull() ? "N/A" : QString::number(elbear["A6_gyro_z"].toDouble(), 'f', 2))
     .arg(elbear["CO30_eco2"].isNull() ? "N/A" : QString::number(elbear["CO30_eco2"].toInt()))
     .arg(elbear["CO30_tvoc"].isNull() ? "N/A" : QString::number(elbear["CO30_tvoc"].toInt()))
     .arg(elbear["D20_distance"].isNull() ? "N/A" : QString::number(elbear["D20_distance"].toInt()))
     .arg(elbear["timestamp"].toString());
    
    m_elbearLabel->setText(elbearText);
    m_lastUpdateLabel->setText("Last update: " + lastUpdate);
}

MainWindow::~MainWindow()
{
}
