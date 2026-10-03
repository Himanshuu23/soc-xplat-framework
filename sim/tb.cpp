#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <vector>

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include "Vsoc_top.h"
#include "Vsoc_top___024root.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

static const int kRamWords = 16384;
static const int kBaudDiv = 16;
static const uint32_t kRamFill = 0xdeadbeef;
static const int kTraceDepth = 99;
static const int kExitTrap = 99;
static const int kExitTimeout = 124;
static const int kExitUsage = 2;
static const int kIdleGrace = 2048;
static const uint64_t kBootLimit = 20000000;

struct Options {
    std::string image;
    std::string vcd = "trace.vcd";
    bool trace = false;
    uint64_t timeout = 5000000;
    uint64_t trace_cycles = 50000;
    int port = -1;
};

class UartDecoder {
public:
    bool step(bool line, uint8_t &out)
    {
        if (state_ == 0) {
            if (!line) {
                state_ = 1;
                count_ = kBaudDiv + kBaudDiv / 2;
                bit_ = 0;
                byte_ = 0;
            }
            return false;
        }
        if (--count_ > 0)
            return false;
        count_ = kBaudDiv;
        if (state_ == 1) {
            byte_ |= (line ? 1 : 0) << bit_;
            if (++bit_ == 8)
                state_ = 2;
            return false;
        }
        state_ = 0;
        out = byte_;
        return line;
    }

    bool active() const { return state_ != 0; }

private:
    int state_ = 0;
    int count_ = 0;
    int bit_ = 0;
    uint8_t byte_ = 0;
};

class UartDriver {
public:
    void push(uint8_t byte) { queue_.push_back(byte); }

    bool active() const { return frame_bits_ != 0 || gap_ > 0 || !queue_.empty(); }

    bool step()
    {
        if (frame_bits_ == 0) {
            if (gap_ > 0) {
                gap_--;
                return true;
            }
            if (queue_.empty())
                return true;
            frame_ = (1 << 9) | (queue_.front() << 1);
            queue_.pop_front();
            frame_bits_ = 10;
            count_ = 0;
        }
        bool line = frame_ & 1;
        if (++count_ == kBaudDiv) {
            count_ = 0;
            frame_ >>= 1;
            if (--frame_bits_ == 0)
                gap_ = 2 * 10 * kBaudDiv;
        }
        return line;
    }

private:
    std::deque<uint8_t> queue_;
    uint16_t frame_ = 0;
    int frame_bits_ = 0;
    int count_ = 0;
    int gap_ = 0;
};

class SocketBridge {
public:
    bool listen_on(int port)
    {
        listen_fd_ = socket(AF_INET, SOCK_STREAM, 0);
        int one = 1;
        setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = htons(port);
        if (bind(listen_fd_, (sockaddr *)&addr, sizeof(addr)) < 0)
            return false;
        return listen(listen_fd_, 1) == 0;
    }

    bool accept_client()
    {
        client_fd_ = accept(listen_fd_, nullptr, nullptr);
        if (client_fd_ < 0)
            return false;
        int one = 1;
        setsockopt(client_fd_, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
        return true;
    }

    void send_byte(uint8_t byte)
    {
        send(client_fd_, &byte, 1, MSG_NOSIGNAL);
    }

    bool wait_data(UartDriver &driver)
    {
        uint8_t buf[256];
        ssize_t n = recv(client_fd_, buf, sizeof(buf), 0);
        if (n <= 0)
            return false;
        for (ssize_t i = 0; i < n; i++)
            driver.push(buf[i]);
        return true;
    }

private:
    int listen_fd_ = -1;
    int client_fd_ = -1;
};

static bool load_image(Vsoc_top *top, const std::string &path)
{
    std::vector<uint32_t> words;
    bool is_hex = path.size() > 4 && path.compare(path.size() - 4, 4, ".hex") == 0;
    FILE *f = fopen(path.c_str(), is_hex ? "r" : "rb");
    if (!f)
        return false;
    if (is_hex) {
        unsigned value;
        while (fscanf(f, "%x", &value) == 1)
            words.push_back(value);
    } else {
        uint8_t bytes[4];
        size_t n;
        while ((n = fread(bytes, 1, 4, f)) > 0) {
            memset(bytes + n, 0, 4 - n);
            words.push_back(bytes[0] | bytes[1] << 8 | bytes[2] << 16 | (uint32_t)bytes[3] << 24);
        }
    }
    fclose(f);
    if (words.size() > (size_t)kRamWords)
        return false;
    for (int i = 0; i < kRamWords; i++)
        top->rootp->soc_top__DOT__u_ram__DOT__mem[i] = kRamFill;
    for (size_t i = 0; i < words.size(); i++)
        top->rootp->soc_top__DOT__u_ram__DOT__mem[i] = words[i];
    return true;
}

static bool parse_args(int argc, char **argv, Options &opt)
{
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--trace")
            opt.trace = true;
        else if (arg == "--vcd" && i + 1 < argc)
            opt.vcd = argv[++i];
        else if (arg == "--trace-cycles" && i + 1 < argc)
            opt.trace_cycles = strtoull(argv[++i], nullptr, 0);
        else if (arg == "--timeout" && i + 1 < argc)
            opt.timeout = strtoull(argv[++i], nullptr, 0);
        else if (arg == "--listen" && i + 1 < argc)
            opt.port = atoi(argv[++i]);
        else if (arg[0] != '-')
            opt.image = arg;
        else
            return false;
    }
    return !opt.image.empty();
}

int main(int argc, char **argv)
{
    Options opt;
    if (!parse_args(argc, argv, opt)) {
        fprintf(stderr, "usage: %s [--trace] [--vcd file] [--trace-cycles n] [--timeout cycles] [--listen port] firmware.{bin,hex}\n", argv[0]);
        return kExitUsage;
    }

    VerilatedContext ctx;
    Vsoc_top top{&ctx};

    if (!load_image(&top, opt.image)) {
        fprintf(stderr, "cannot load %s\n", opt.image.c_str());
        return kExitUsage;
    }

    VerilatedVcdC *tfp = nullptr;
    if (opt.trace) {
        ctx.traceEverOn(true);
        tfp = new VerilatedVcdC;
        top.trace(tfp, kTraceDepth);
        tfp->open(opt.vcd.c_str());
    }

    SocketBridge bridge;
    bool socket_mode = opt.port >= 0;
    if (socket_mode) {
        if (!bridge.listen_on(opt.port)) {
            fprintf(stderr, "cannot listen on port %d\n", opt.port);
            return kExitUsage;
        }
        printf("[tb] listening on port %d\n", opt.port);
        fflush(stdout);
        if (!bridge.accept_client()) {
            fprintf(stderr, "accept failed\n");
            return kExitUsage;
        }
        opt.timeout = 0;
    }

    UartDecoder decoder;
    UartDriver driver;
    top.resetn = 0;
    top.uart_rx = 1;

    uint64_t cycle = 0;
    uint64_t idle = 0;
    int code = 0;
    bool finished = false;
    bool booted = false;

    while (!finished) {
        top.resetn = cycle >= 8;
        top.uart_rx = driver.step();

        bool tracing = tfp && cycle < opt.trace_cycles;
        top.clk = 0;
        top.eval();
        if (tracing)
            tfp->dump(ctx.time());
        ctx.timeInc(1);
        top.clk = 1;
        top.eval();
        if (tracing)
            tfp->dump(ctx.time());
        ctx.timeInc(1);
        cycle++;

        uint8_t byte;
        bool got_byte = decoder.step(top.uart_tx, byte);
        if (got_byte) {
            booted = true;
            if (socket_mode) {
                bridge.send_byte(byte);
            } else {
                putchar(byte);
                fflush(stdout);
            }
        }

        bool busy = got_byte || decoder.active() || driver.active();
        idle = busy ? 0 : idle + 1;

        if (socket_mode && booted && idle >= kIdleGrace) {
            if (!bridge.wait_data(driver))
                finished = true;
            idle = 0;
        } else if (socket_mode && !booted && cycle >= kBootLimit) {
            printf("[tb] firmware never started the UART\n");
            code = kExitTimeout;
            finished = true;
        } else if (top.sim_exit) {
            code = (int)top.sim_exit_code;
            finished = true;
        } else if (top.trap && cycle > 8) {
            printf("[tb] CPU trap\n");
            code = kExitTrap;
            finished = true;
        } else if (opt.timeout && cycle >= opt.timeout) {
            printf("[tb] timeout after %llu cycles\n", (unsigned long long)cycle);
            code = kExitTimeout;
            finished = true;
        }
    }

    if (tfp) {
        tfp->close();
        delete tfp;
    }
    top.final();
    printf("[tb] exit code %d after %llu cycles\n", code, (unsigned long long)cycle);
    return code;
}
