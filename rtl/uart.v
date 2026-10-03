module uart #(
    parameter DEFAULT_BAUD = 16
) (
    input clk,
    input resetn,
    input en,
    input [3:0] wstrb,
    input [3:0] addr,
    input [31:0] wdata,
    output reg [31:0] rdata,
    output tx,
    input rx
);
    localparam REG_DATA = 2'd0;
    localparam REG_STATUS = 2'd1;
    localparam REG_BAUD = 2'd2;

    wire wr = en && |wstrb;
    wire rd = en && !(|wstrb);
    wire [1:0] reg_sel = addr[3:2];

    reg [15:0] baud;

    reg tx_busy;
    reg [15:0] tx_cnt;
    reg [3:0] tx_bits;
    reg [9:0] tx_shift;
    assign tx = tx_busy ? tx_shift[0] : 1'b1;

    reg rx_sync0, rx_sync1;
    reg [1:0] rx_state;
    reg [15:0] rx_cnt;
    reg [3:0] rx_bits;
    reg [7:0] rx_shift;
    reg [7:0] rx_data;
    reg rx_valid;

    always @* begin
        case (reg_sel)
            REG_DATA: rdata = {24'd0, rx_data};
            REG_STATUS: rdata = {30'd0, rx_valid, tx_busy};
            REG_BAUD: rdata = {16'd0, baud};
            default: rdata = 32'd0;
        endcase
    end

    always @(posedge clk) begin
        if (!resetn) begin
            baud <= DEFAULT_BAUD;
            tx_busy <= 0;
            tx_cnt <= 0;
            tx_bits <= 0;
            tx_shift <= 10'h3ff;
            rx_sync0 <= 1;
            rx_sync1 <= 1;
            rx_state <= 0;
            rx_cnt <= 0;
            rx_bits <= 0;
            rx_shift <= 0;
            rx_data <= 0;
            rx_valid <= 0;
        end else begin
            if (wr && reg_sel == REG_BAUD) baud <= wdata[15:0];

            if (wr && reg_sel == REG_DATA && !tx_busy) begin
                tx_shift <= {1'b1, wdata[7:0], 1'b0};
                tx_bits <= 10;
                tx_cnt <= baud - 1;
                tx_busy <= 1;
            end else if (tx_busy) begin
                if (tx_cnt == 0) begin
                    tx_cnt <= baud - 1;
                    tx_shift <= {1'b1, tx_shift[9:1]};
                    tx_bits <= tx_bits - 1;
                    if (tx_bits == 1) tx_busy <= 0;
                end else begin
                    tx_cnt <= tx_cnt - 1;
                end
            end

            rx_sync0 <= rx;
            rx_sync1 <= rx_sync0;
            if (rd && reg_sel == REG_DATA) rx_valid <= 0;

            case (rx_state)
                0: if (!rx_sync1) begin
                    rx_state <= 1;
                    rx_cnt <= baud + (baud >> 1) - 1;
                    rx_bits <= 0;
                end
                1: if (rx_cnt == 0) begin
                    rx_shift <= {rx_sync1, rx_shift[7:1]};
                    rx_cnt <= baud - 1;
                    rx_bits <= rx_bits + 1;
                    if (rx_bits == 7) begin
                        rx_data <= {rx_sync1, rx_shift[7:1]};
                        rx_valid <= 1;
                        rx_state <= 2;
                    end
                end else begin
                    rx_cnt <= rx_cnt - 1;
                end
                2: if (rx_cnt == 0) rx_state <= 0;
                   else rx_cnt <= rx_cnt - 1;
                default: rx_state <= 0;
            endcase
        end
    end
endmodule
