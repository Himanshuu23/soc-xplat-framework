module soc_top (
    input clk,
    input resetn,
    output uart_tx,
    input uart_rx,
    output reg sim_exit,
    output reg [31:0] sim_exit_code,
    output trap
);
    wire mem_valid;
    wire mem_instr;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [3:0] mem_wstrb;
    wire mem_ready;
    wire [31:0] mem_rdata;

    wire timer_irq;
    wire dma_irq;
    wire [31:0] irq = {30'd0, dma_irq, timer_irq};

    picorv32 #(
        .ENABLE_COUNTERS(0),
        .ENABLE_COUNTERS64(0),
        .BARREL_SHIFTER(1),
        .ENABLE_IRQ(1),
        .ENABLE_IRQ_TIMER(0),
        .LATCHED_IRQ(32'hffff_fffc),
        .PROGADDR_RESET(32'h0000_0000),
        .PROGADDR_IRQ(32'h0000_0010),
        .STACKADDR(32'hffff_ffff)
    ) u_cpu (
        .clk(clk),
        .resetn(resetn),
        .trap(trap),
        .mem_valid(mem_valid),
        .mem_instr(mem_instr),
        .mem_ready(mem_ready),
        .mem_addr(mem_addr),
        .mem_wdata(mem_wdata),
        .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata),
        .irq(irq)
    );

    wire sel_ram = mem_addr[31:16] == 16'h0000;
    wire sel_uart = mem_addr[31:12] == 20'h10000;
    wire sel_timer = mem_addr[31:12] == 20'h10001;
    wire sel_dma = mem_addr[31:12] == 20'h10002;
    wire sel_sys = mem_addr[31:12] == 20'h10003;

    wire dma_req;
    wire dma_we;
    wire [31:0] dma_addr;
    wire [31:0] dma_wdata;
    reg cpu_ack;
    reg dma_ack;
    reg last_was_dma;

    wire cpu_ram_req = mem_valid && sel_ram && !cpu_ack;
    wire grant_dma = dma_req && !dma_ack && (!cpu_ram_req || !last_was_dma);
    wire grant_cpu = cpu_ram_req && !grant_dma;

    wire [31:0] ram_rdata;

    ram u_ram (
        .clk(clk),
        .en(grant_cpu || grant_dma),
        .we(grant_dma ? {4{dma_we}} : mem_wstrb),
        .addr(grant_dma ? dma_addr[15:2] : mem_addr[15:2]),
        .wdata(grant_dma ? dma_wdata : mem_wdata),
        .rdata(ram_rdata)
    );

    always @(posedge clk) begin
        cpu_ack <= resetn && grant_cpu;
        dma_ack <= resetn && grant_dma;
        if (!resetn) last_was_dma <= 0;
        else if (grant_dma) last_was_dma <= 1;
        else if (grant_cpu) last_was_dma <= 0;
    end

    reg io_ready;
    reg [31:0] io_rdata;
    wire io_en = mem_valid && !sel_ram && !io_ready;
    wire [31:0] uart_rdata;
    wire [31:0] timer_rdata;
    wire [31:0] dma_rdata;

    uart u_uart (
        .clk(clk),
        .resetn(resetn),
        .en(io_en && sel_uart),
        .wstrb(mem_wstrb),
        .addr(mem_addr[3:0]),
        .wdata(mem_wdata),
        .rdata(uart_rdata),
        .tx(uart_tx),
        .rx(uart_rx)
    );

    timer u_timer (
        .clk(clk),
        .resetn(resetn),
        .en(io_en && sel_timer),
        .wstrb(mem_wstrb),
        .addr(mem_addr[3:0]),
        .wdata(mem_wdata),
        .rdata(timer_rdata),
        .irq(timer_irq)
    );

    dma u_dma (
        .clk(clk),
        .resetn(resetn),
        .en(io_en && sel_dma),
        .wstrb(mem_wstrb),
        .addr(mem_addr[4:0]),
        .wdata(mem_wdata),
        .rdata(dma_rdata),
        .irq(dma_irq),
        .req(dma_req),
        .we(dma_we),
        .maddr(dma_addr),
        .mwdata(dma_wdata),
        .ack(dma_ack),
        .mrdata(ram_rdata)
    );

    always @(posedge clk) begin
        io_ready <= resetn && io_en;
        io_rdata <= sel_uart ? uart_rdata :
                    sel_timer ? timer_rdata :
                    sel_dma ? dma_rdata : 32'd0;
        if (!resetn) begin
            sim_exit <= 0;
            sim_exit_code <= 0;
        end else if (io_en && sel_sys && |mem_wstrb) begin
            sim_exit <= 1;
            sim_exit_code <= mem_wdata;
        end
    end

    assign mem_ready = cpu_ack || io_ready;
    assign mem_rdata = cpu_ack ? ram_rdata : io_rdata;
endmodule
