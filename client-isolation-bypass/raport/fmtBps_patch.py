

def fmtBps(bps, fmt):
    """Format bits per second."""
    bps = float(bps)
    if bps >= 1e9:
        return '%.1f Gbps' % (bps / 1e9)
    elif bps >= 1e6:
        return '%.1f Mbps' % (bps / 1e6)
    elif bps >= 1e3:
        return '%.1f Kbps' % (bps / 1e3)
    return '%.1f bps' % bps
