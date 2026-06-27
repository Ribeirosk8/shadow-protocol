// =============================================================================
// SHADOW-Net — FANET Network Topology (OMNeT++ / INET)
// =============================================================================
// Paper: "SHADOW-Net: Delay-Aware Dynamic SMPC and Opportunistic Caching
//         in Privacy-Preserving FANETs"
// Author: Amauri Ribeiro
//
// Defines a 3D urban airspace MANET with 5 mobile UAV nodes.
//
// Architecture (Paper §III-A):
//   - IEEE 802.11 Ad-Hoc MAC layer (no AP / infrastructure)
//   - AODV reactive routing for multi-hop FANET
//   - 3D mobility (RandomWaypointMobility) with altitude constraints
//   - Ieee80211ScalarRadioMedium for realistic channel propagation
//
// Future Work (Paper §VI):
//   "deploy SHADOW-Net within an OMNeT++ simulator to measure the exact
//    Packet Delivery Ratio (PDR) and Joules saved under hostile channel
//    fading conditions."
// =============================================================================

package shadownet;

// ─── INET Framework Imports ─────────────────────────────────────────────────
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.inet.AdhocHost;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import inet.visualizer.common.IntegratedVisualizer;


// =============================================================================
// ShadowManet — 3D Airspace FANET
// =============================================================================
// 5 UAV nodes in a 1000m × 1000m × 500m urban airspace volume.
// Each UAV carries:
//   • 1× IEEE 802.11 wireless NIC (Ad-Hoc mode)
//   • AODV routing module for FANET multi-hop
//   • UDP application layer for SMPC matrix exchange
//   • 3D RandomWaypointMobility for realistic flight patterns
//
// The RadioMedium handles signal propagation, path loss, interference,
// and the MAC-layer overhearing that SHADOW-Net §IV-C mitigates.
// =============================================================================

network ShadowManet
{
    parameters:
        // ── Simulation parameters (overridable in omnetpp.ini) ──────────
        int numUavs = default(5);       // Number of UAV nodes in the swarm

        // ── 3D Airspace dimensions ──────────────────────────────────────
        // Urban corridor: 1 km × 1 km ground area, 500 m altitude ceiling
        @display("bgb=1000,1000;bgi=background/terrain,s");

    submodules:
        // ── Infrastructure modules ──────────────────────────────────────

        // Auto-assigns IPv4 addresses for the ad-hoc network.
        // In a real FANET these would be link-local or mDNS-assigned.
        configurator: Ipv4NetworkConfigurator {
            @display("p=900,50;is=s");
        }

        // Models IEEE 802.11 signal propagation, path loss, fading,
        // and the MAC-layer overhearing (Paper §III-A, §IV-C).
        radioMedium: Ieee80211ScalarRadioMedium {
            @display("p=900,150;is=s");
        }

        // Integrated 2D/3D visualizer (requires OSG for 3D globe view).
        visualizer: IntegratedVisualizer {
            @display("p=900,250;is=s");
        }

        // ── UAV Swarm (FANET nodes) ─────────────────────────────────────
        // AdhocHost includes:
        //   • IEEE 802.11 wireless NIC (wlan[0])
        //   • IPv4 network layer
        //   • Configurable routing (AODV via omnetpp.ini)
        //   • UDP/TCP transport layer
        //   • Mobility module (set in omnetpp.ini)
        uav[numUavs]: AdhocHost {
            @display("i=device/drone;r=200,,#40e0d0,1");
        }

    // No explicit connections required — wireless links are mediated
    // by the Ieee80211ScalarRadioMedium module.
}
