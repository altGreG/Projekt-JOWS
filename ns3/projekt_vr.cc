#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"
#include "ns3/ipv4-global-routing-helper.h"
#include "ns3/flow-monitor-module.h"
#include <fstream>
#include <filesystem>   // C++17

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("Wifi6_VR_Bursty_Simulation");

int main(int argc, char *argv[])
{
    uint32_t vrStations = 1;
    uint32_t bgStations = 1;
    uint16_t vrPort = 5000;
    uint16_t bgPort = 9000;
    double frameInterval = 1.0 / 60.0;
    // uint32_t packetSize = 1200;
    // uint32_t packetsPerFrame = 8;
    uint32_t packetSize = 1500;
    uint32_t packetsPerFrame = 18; 

    bool enableQos = false;
    bool enableAggregation = false;
    uint32_t maxAmpduSize = 65535;  // Max A-MPDU size in bytes

    std::string outputDir = "./results";
    std::string csvFileName = "results.csv";
    std::string xmlFileName = "results.xml";

    CommandLine cmd(__FILE__);
    cmd.AddValue("vrStations", "Number of VR stations", vrStations);
    cmd.AddValue("bgStations", "Number of Background stations", bgStations);
    cmd.AddValue("enableQos", "Enable QoS Prioritization for VR", enableQos);
    cmd.AddValue("enableAggregation", "Enable Aggregation for VR", enableAggregation);
    cmd.AddValue("maxAmpduSize", "Max A-MPDU size in bytes", maxAmpduSize);
    cmd.AddValue("outputDir", "Directory for output files", outputDir);
    cmd.AddValue("csvFileName", "CSV output filename", csvFileName);
    cmd.AddValue("xmlFileName", "XML output filename", xmlFileName);

    cmd.Parse(argc, argv);
    std::filesystem::create_directories(outputDir);

    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer vrStaNodes;
    vrStaNodes.Create(vrStations);
    NodeContainer bgStaNodes;
    bgStaNodes.Create(bgStations);
    NodeContainer allStaNodes;
    allStaNodes.Add(vrStaNodes);
    allStaNodes.Add(bgStaNodes);

    YansWifiChannelHelper channel;
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::LogDistancePropagationLossModel", "Exponent", DoubleValue(3.0));

    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());
    phy.Set("ChannelSettings", StringValue("{42, 80, BAND_5GHZ, 0}"));

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211ax);
    wifi.SetRemoteStationManager("ns3::IdealWifiManager");

    Ssid ssid = Ssid("VR-WIFI6");
    WifiMacHelper mac;
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer staDevices = wifi.Install(phy, mac, allStaNodes);

    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDevice = wifi.Install(phy, mac, apNode);

    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(apNode);
    mobility.Install(allStaNodes);

    Ptr<UniformRandomVariable> angle = CreateObject<UniformRandomVariable>();
    Ptr<UniformRandomVariable> dist = CreateObject<UniformRandomVariable>();
    dist->SetAttribute("Min", DoubleValue(5.0));
    dist->SetAttribute("Max", DoubleValue(15.0));

    for (uint32_t i = 0; i < allStaNodes.GetN(); i++) {
        double a = angle->GetValue(0.0, 2 * M_PI);
        double r = dist->GetValue();
        allStaNodes.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(r * cos(a), r * sin(a), 0.0));
    }

    InternetStackHelper stack;
    stack.Install(apNode);
    stack.Install(allStaNodes);

    Ipv4AddressHelper address;
    address.SetBase("192.168.1.0", "255.255.255.0");
    Ipv4InterfaceContainer staIf = address.Assign(staDevices);
    Ipv4InterfaceContainer apIf = address.Assign(apDevice);
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    // Print configuration and QoS settings
    NS_LOG_UNCOND("=== Simulation configuration ===");
    NS_LOG_UNCOND("VR stations: " << vrStations);
    NS_LOG_UNCOND("Background stations: " << bgStations);
    NS_LOG_UNCOND("VR port: " << vrPort << ", BG port: " << bgPort);
    NS_LOG_UNCOND("Packet size: " << packetSize << " bytes");
    NS_LOG_UNCOND("Packets per frame: " << packetsPerFrame);
    NS_LOG_UNCOND("Frame interval: " << frameInterval << " s");
    NS_LOG_UNCOND("QoS enabled: " << (enableQos ? "true" : "false"));
    if (enableQos) {
        NS_LOG_UNCOND("VR UDP TOS value: 0xC0");
    }
    NS_LOG_UNCOND("Aggregation enabled: " << (enableAggregation ? "true" : "false"));
    if (enableAggregation) {
        NS_LOG_UNCOND("Max A-MPDU size: " << maxAmpduSize << " bytes");
    }

    // Configure A-MPDU if enabled
    if (enableAggregation) {
        NetDeviceContainer allDevices;
        allDevices.Add(staDevices);
        allDevices.Add(apDevice);
        for (uint32_t i = 0; i < allDevices.GetN(); i++) {
            Ptr<WifiNetDevice> wifiDev = DynamicCast<WifiNetDevice>(allDevices.Get(i));
            if (wifiDev) {
                Ptr<WifiMac> mac = wifiDev->GetMac();
                if (mac) {
                    mac->SetAttribute("BE_MaxAmpduSize", UintegerValue(maxAmpduSize));
                    mac->SetAttribute("VI_MaxAmpduSize", UintegerValue(maxAmpduSize));
                    mac->SetAttribute("VO_MaxAmpduSize", UintegerValue(maxAmpduSize));
                    mac->SetAttribute("BK_MaxAmpduSize", UintegerValue(maxAmpduSize));
                }
            }
        }

        NS_LOG_UNCOND("=== A-MPDU configuration per Wifi device ===");
        for (uint32_t i = 0; i < allDevices.GetN(); i++) {
            Ptr<WifiNetDevice> wifiDev = DynamicCast<WifiNetDevice>(allDevices.Get(i));
            if (wifiDev) {
                Ptr<WifiMac> mac = wifiDev->GetMac();
                if (mac) {
                    UintegerValue beSize, bkSize, viSize, voSize;
                    mac->GetAttribute("BE_MaxAmpduSize", beSize);
                    mac->GetAttribute("BK_MaxAmpduSize", bkSize);
                    mac->GetAttribute("VI_MaxAmpduSize", viSize);
                    mac->GetAttribute("VO_MaxAmpduSize", voSize);
                    NS_LOG_UNCOND("Device " << i << " [" << wifiDev->GetTypeId().GetName() << "] - BE="
                        << beSize.Get() << " BK=" << bkSize.Get() << " VI=" << viSize.Get()
                        << " VO=" << voSize.Get());
                }
            }
        }
    }

    // VR SERVER
    UdpServerHelper vrServer(vrPort);
    ApplicationContainer vrServerApp = vrServer.Install(apNode.Get(0));
    vrServerApp.Start(Seconds(0.5));
    vrServerApp.Stop(Seconds(20.0));

    // VR CLIENTS
    for (uint32_t i = 0; i < vrStaNodes.GetN(); i++) {
        
        // --- ROZWI\u0104ZANIE PANCERNE (Tagowanie docelowego adresu IP) ---
        InetSocketAddress destAddress(apIf.GetAddress(0), vrPort);
        if (enableQos) {
            destAddress.SetTos(0xC0);
        }
        
        // Przekazujemy adres ze znacznikiem bezpo\u015brednio do klienta UDP
        UdpClientHelper client(destAddress);
        // --------------------------------------------------------------
        
        client.SetAttribute("MaxPackets", UintegerValue(1000000));
        client.SetAttribute("PacketSize", UintegerValue(packetSize));
        client.SetAttribute("Interval", TimeValue(Seconds(frameInterval / packetsPerFrame)));
        
        ApplicationContainer app = client.Install(vrStaNodes.Get(i));
        app.Start(Seconds(1.0));
        app.Stop(Seconds(20.0));
    }

    // BACKGROUND TCP SERVER
    PacketSinkHelper tcpSink("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), bgPort));
    ApplicationContainer bgServer = tcpSink.Install(apNode.Get(0));
    bgServer.Start(Seconds(0.5));
    bgServer.Stop(Seconds(20.0));

    // BACKGROUND CLIENTS
    for (uint32_t i = 0; i < bgStaNodes.GetN(); i++) {
        BulkSendHelper bgClient("ns3::TcpSocketFactory", InetSocketAddress(apIf.GetAddress(0), bgPort));
        bgClient.SetAttribute("MaxBytes", UintegerValue(0));
        
        ApplicationContainer app = bgClient.Install(bgStaNodes.Get(i));
        app.Start(Seconds(1.0));
        app.Stop(Seconds(20.0));
    }

    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    Simulator::Stop(Seconds(20.0));
    Simulator::Run();


    monitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());

    // Auto-nazwy plików, jeśli użytkownik nie podał własnych
    if (xmlFileName == "results.xml") {
        xmlFileName = enableQos ? "qos_enabled_results.xml" : "qos_disabled_results.xml";
    }
    if (csvFileName == "results.csv") {
        csvFileName = enableQos ? "qos_enabled_results.csv" : "qos_disabled_results.csv";
    }
    std::string xmlPath = outputDir + "/" + xmlFileName;
    std::string csvPath = outputDir + "/" + csvFileName;

    // Lambda licząca metryki dla pojedynczego flow
    auto computeMetrics = [](const FlowMonitor::FlowStats &fs) {
        struct Metrics {
            double durationSec;
            double throughputMbps;
            double avgDelayMs;
            double avgJitterMs;
            double lossRatio;
            double meanPacketSize;
        } m{};

        m.durationSec = (fs.timeLastRxPacket - fs.timeFirstTxPacket).GetSeconds();
        m.throughputMbps = (m.durationSec > 0)
            ? (fs.rxBytes * 8.0) / m.durationSec / 1e6
            : 0.0;
        m.avgDelayMs  = (fs.rxPackets > 0)
            ? (fs.delaySum.GetSeconds() / fs.rxPackets) * 1000.0
            : 0.0;
        m.avgJitterMs = (fs.rxPackets > 1)
            ? (fs.jitterSum.GetSeconds() / (fs.rxPackets - 1)) * 1000.0
            : 0.0;
        m.lossRatio = (fs.txPackets > 0)
            ? (double)fs.lostPackets / fs.txPackets
            : 0.0;
        m.meanPacketSize = (fs.rxPackets > 0)
            ? (double)fs.rxBytes / fs.rxPackets
            : 0.0;
        return m;
    };

    // === Wypisanie wyników na konsolę ===
    NS_LOG_UNCOND("");
    NS_LOG_UNCOND("=================== Flow monitor summary ===================");

    // Agregaty osobno dla VR i tła
    double vrTotalThroughput = 0.0, bgTotalThroughput = 0.0;
    double vrSumDelay = 0.0, vrSumJitter = 0.0, vrSumLoss = 0.0;
    double bgSumDelay = 0.0, bgSumJitter = 0.0, bgSumLoss = 0.0;
    uint32_t vrFlowCount = 0, bgFlowCount = 0;
    uint64_t vrTxPackets = 0, vrRxPackets = 0, vrLostPackets = 0;
    uint64_t bgTxPackets = 0, bgRxPackets = 0, bgLostPackets = 0;

    if (classifier) {
        auto stats = monitor->GetFlowStats();
        for (auto const &flow : stats) {
            Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(flow.first);
            const FlowMonitor::FlowStats &fs = flow.second;
            bool isVr = (t.destinationPort == vrPort);
            std::string flowType = isVr ? "VR UDP" : "background TCP";
            auto m = computeMetrics(fs);

            NS_LOG_UNCOND("--- Flow " << flow.first << " (" << flowType << ") ---");
            NS_LOG_UNCOND("  " << t.sourceAddress << ":" << t.sourcePort
                << " -> " << t.destinationAddress << ":" << t.destinationPort
                << "  protocol=" << (uint32_t)t.protocol);
            NS_LOG_UNCOND("  Tx packets:        " << fs.txPackets);
            NS_LOG_UNCOND("  Rx packets:        " << fs.rxPackets);
            NS_LOG_UNCOND("  Lost packets:      " << fs.lostPackets);
            NS_LOG_UNCOND("  Tx bytes:          " << fs.txBytes);
            NS_LOG_UNCOND("  Rx bytes:          " << fs.rxBytes);
            NS_LOG_UNCOND("  Duration:          " << m.durationSec << " s");
            NS_LOG_UNCOND("  Throughput:        " << m.throughputMbps << " Mb/s");
            NS_LOG_UNCOND("  Avg delay:         " << m.avgDelayMs << " ms");
            NS_LOG_UNCOND("  Avg jitter:        " << m.avgJitterMs << " ms");
            NS_LOG_UNCOND("  Loss ratio:        " << m.lossRatio * 100.0 << " %");
            NS_LOG_UNCOND("  Mean packet size:  " << m.meanPacketSize << " B");

            if (isVr) {
                vrTotalThroughput += m.throughputMbps;
                vrSumDelay  += m.avgDelayMs;
                vrSumJitter += m.avgJitterMs;
                vrSumLoss   += m.lossRatio;
                vrFlowCount++;
                vrTxPackets   += fs.txPackets;
                vrRxPackets   += fs.rxPackets;
                vrLostPackets += fs.lostPackets;
            } else {
                bgTotalThroughput += m.throughputMbps;
                bgSumDelay  += m.avgDelayMs;
                bgSumJitter += m.avgJitterMs;
                bgSumLoss   += m.lossRatio;
                bgFlowCount++;
                bgTxPackets   += fs.txPackets;
                bgRxPackets   += fs.rxPackets;
                bgLostPackets += fs.lostPackets;
            }
        }

        NS_LOG_UNCOND("");
        NS_LOG_UNCOND("=================== Aggregated metrics ===================");
        if (vrFlowCount > 0) {
            NS_LOG_UNCOND("VR flows: " << vrFlowCount);
            NS_LOG_UNCOND("  Total throughput:  " << vrTotalThroughput << " Mb/s");
            NS_LOG_UNCOND("  Avg delay:         " << vrSumDelay  / vrFlowCount << " ms");
            NS_LOG_UNCOND("  Avg jitter:        " << vrSumJitter / vrFlowCount << " ms");
            NS_LOG_UNCOND("  Avg loss ratio:    " << (vrSumLoss / vrFlowCount) * 100.0 << " %");
            NS_LOG_UNCOND("  Total Tx/Rx/Lost:  " << vrTxPackets << " / "
                                                  << vrRxPackets << " / " << vrLostPackets);
        }
        if (bgFlowCount > 0) {
            NS_LOG_UNCOND("Background flows: " << bgFlowCount);
            NS_LOG_UNCOND("  Total throughput:  " << bgTotalThroughput << " Mb/s");
            NS_LOG_UNCOND("  Avg delay:         " << bgSumDelay  / bgFlowCount << " ms");
            NS_LOG_UNCOND("  Avg jitter:        " << bgSumJitter / bgFlowCount << " ms");
            NS_LOG_UNCOND("  Avg loss ratio:    " << (bgSumLoss / bgFlowCount) * 100.0 << " %");
            NS_LOG_UNCOND("  Total Tx/Rx/Lost:  " << bgTxPackets << " / "
                                                  << bgRxPackets << " / " << bgLostPackets);
        }
    } else {
        NS_LOG_UNCOND("Flow monitor classifier is not an IPv4 flow classifier.");
    }

    // === Zapis XML ===
    monitor->SerializeToXmlFile(xmlPath, true, true);
    NS_LOG_UNCOND("");
    NS_LOG_UNCOND("Saved flow monitor XML to " << xmlPath);

    // === Zapis CSV ===
    std::ofstream csvFile(csvPath);
    if (csvFile.is_open()) {
        csvFile << "FlowId,Type,Source,SourcePort,Destination,DestinationPort,Protocol,"
                << "TxPackets,RxPackets,LostPackets,TxBytes,RxBytes,"
                << "TimeFirstTxPacket_s,TimeFirstRxPacket_s,TimeLastTxPacket_s,TimeLastRxPacket_s,"
                << "DurationSeconds,ThroughputMbps,AvgDelayMs,AvgJitterMs,LossRatio,MeanPacketSizeBytes\n";

        if (classifier) {
            auto stats = monitor->GetFlowStats();
            for (auto const &flow : stats) {
                Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(flow.first);
                const FlowMonitor::FlowStats &fs = flow.second;
                std::string flowType = (t.destinationPort == vrPort ? "VR UDP" : "background TCP");
                auto m = computeMetrics(fs);

                csvFile << flow.first << "," << flowType << ","
                        << t.sourceAddress << "," << t.sourcePort << ","
                        << t.destinationAddress << "," << t.destinationPort << ","
                        << (uint32_t)t.protocol << ","
                        << fs.txPackets << "," << fs.rxPackets << "," << fs.lostPackets << ","
                        << fs.txBytes << "," << fs.rxBytes << ","
                        << fs.timeFirstTxPacket.GetSeconds() << ","
                        << fs.timeFirstRxPacket.GetSeconds() << ","
                        << fs.timeLastTxPacket.GetSeconds()  << ","
                        << fs.timeLastRxPacket.GetSeconds()  << ","
                        << m.durationSec   << ","
                        << m.throughputMbps << ","
                        << m.avgDelayMs    << ","
                        << m.avgJitterMs   << ","
                        << m.lossRatio     << ","
                        << m.meanPacketSize << "\n";
            }
        }
        csvFile.close();
        NS_LOG_UNCOND("Saved flow monitor CSV to " << csvPath);
    } else {
        NS_LOG_UNCOND("Unable to open " << csvPath << " for CSV output.");
    }

    Simulator::Destroy();
    return 0;
}