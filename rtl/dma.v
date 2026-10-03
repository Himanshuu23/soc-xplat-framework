module dma (
    input clk,
    input resetn,
    input en,
    input [3:0] wstrb,
    input [4:0] addr,
    input [31:0] wdata,
    output reg [31:0] rdata,
    output irq,
    output req,
    output we,
    output [31:0] maddr,
    output [31:0] mwdata,
    input ack,
    input [31:0] mrdata
);
    localparam REG_SRC = 3'd0;
    localparam REG_DST = 3'd1;
    localparam REG_LEN = 3'd2;
    localparam REG_CTRL = 3'd3;
    localparam REG_STATUS = 3'd4;

    localparam S_IDLE = 2'd0;
    localparam S_READ = 2'd1;
    localparam S_WRITE = 2'd2;

    wire wr = en && |wstrb;
    wire [2:0] reg_sel = addr[4:2];

    reg [31:0] src;
    reg [31:0] dst;
    reg [31:0] len;
    reg irq_en;
    reg busy;
    reg done;

    reg [1:0] state;
    reg [31:0] cur_src;
    reg [31:0] cur_dst;
    reg [31:0] remaining;
    reg [31:0] data;

    assign req = state == S_READ || state == S_WRITE;
    assign we = state == S_WRITE;
    assign maddr = state == S_WRITE ? cur_dst : cur_src;
    assign mwdata = data;
    assign irq = done && irq_en;

    always @* begin
        case (reg_sel)
            REG_SRC: rdata = src;
            REG_DST: rdata = dst;
            REG_LEN: rdata = len;
            REG_CTRL: rdata = {30'd0, irq_en, 1'b0};
            REG_STATUS: rdata = {30'd0, done, busy};
            default: rdata = 32'd0;
        endcase
    end

    always @(posedge clk) begin
        if (!resetn) begin
            src <= 0;
            dst <= 0;
            len <= 0;
            irq_en <= 0;
            busy <= 0;
            done <= 0;
            state <= S_IDLE;
            cur_src <= 0;
            cur_dst <= 0;
            remaining <= 0;
            data <= 0;
        end else begin
            if (wr && reg_sel == REG_STATUS && wdata[1]) done <= 0;

            if (wr && !busy) begin
                case (reg_sel)
                    REG_SRC: src <= wdata;
                    REG_DST: dst <= wdata;
                    REG_LEN: len <= wdata;
                    default: ;
                endcase
            end
            if (wr && reg_sel == REG_CTRL) irq_en <= wdata[1];

            case (state)
                S_IDLE: begin
                    if (wr && reg_sel == REG_CTRL && wdata[0]) begin
                        if (len == 0) begin
                            done <= 1;
                        end else begin
                            cur_src <= src;
                            cur_dst <= dst;
`ifdef INJECT_DMA_LEN_OFF_BY_ONE
                            remaining <= len + 1;
`else
                            remaining <= len;
`endif
                            busy <= 1;
                            state <= S_READ;
                        end
                    end
                end
                S_READ: begin
                    if (ack) begin
                        data <= mrdata;
                        state <= S_WRITE;
                    end
                end
                S_WRITE: begin
                    if (ack) begin
                        cur_src <= cur_src + 4;
                        cur_dst <= cur_dst + 4;
                        remaining <= remaining - 1;
                        if (remaining == 1) begin
                            busy <= 0;
                            done <= 1;
                            state <= S_IDLE;
                        end else begin
                            state <= S_READ;
                        end
                    end
                end
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
