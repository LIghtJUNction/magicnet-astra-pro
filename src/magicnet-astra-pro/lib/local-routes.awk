# iproute2 emits numeric destinations. Reject incomplete or malformed local
# route output before changing NAT, and never pass a name to xtables.
function ipv4(s, n,a,i) {
    n=split(s,a,"[.]")
    if (n!=4) return 0
    for (i=1;i<=4;i++)
        if (a[i]!~/^[0-9]+$/ || length(a[i])>3 || a[i]+0>255 || a[i]~/^0[0-9]/) return 0
    return 1
}
function groups(s, n,a,i) {
    if (s=="") return 0
    n=split(s,a,":")
    for (i=1;i<=n;i++)
        if (a[i]!~/^[0-9a-fA-F]+$/ || length(a[i])>4) return -1
    return n
}
function ipv6(s, k,l,r,v4) {
    if (s ~ /[.]/) {
        v4=s; sub(/^.*:/,"",v4)
        if (!ipv4(v4) || s==v4) return 0
        s=substr(s,1,length(s)-length(v4)) "0:0"
    }
    k=index(s,"::")
    if (!k) return groups(s)==8
    l=groups(substr(s,1,k-1)); r=groups(substr(s,k+2))
    return l>=0 && r>=0 && l+r<8
}
$1=="local" {
    dest=$2
    if (dest=="default") dest=(family=="iptables"?"0.0.0.0/0":"::/0")
    n=split(dest,parts,"/")
    if (n>2 || (n==2 && (parts[2]!~/^[0-9]+$/ || length(parts[2])>3 ||
        parts[2]+0>(family=="iptables"?32:128)))) {bad=1; exit}
    if (!(family=="iptables" ? ipv4(parts[1]) : ipv6(parts[1]))) {bad=1; exit}
    if (!record[dest]++) print dest
    found=1
}
END { if (bad || !found) exit 1 }
