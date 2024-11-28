package tb_tasks;

  localparam CAL_GYRO =  16'h2000;

  localparam POS_ACK   = 8'hA5;
  
  // Task to initialize all input signals to default values.
  task automatic Initialize(ref clk, ref RST_n, ref send_cmd, ref [15:0] cmd);
    begin
        // Initialize all signals to the default values.
        clk = 1'b0;
        RST_n = 1'b0;
        send_cmd = 1'b0;
        cmd = 16'h0000;
        repeat (2) @(posedge clk); // Wait for a full clock cycle for system to reset.
        @(negedge clk); 
        RST_n = 1'b1; // Deassert RST_n on negative edge of clock.
        repeat (500) @(negedge clk); // Wait for a while.
    end
  endtask

  // Task to wait for a signal to be asserted, otherwise times out.
  task automatic TimeoutTask(ref sig, ref clk, input int clks2wait, input string signal);
    fork
      begin : timeout
        repeat(clks2wait) @(posedge clk);
        $display("ERROR: %s not getting asserted and/or held at its value.", signal);
        $stop(); // Stop simulation on error.
      end : timeout
      begin
        @(posedge sig) disable timeout; // Disable timeout if sig is asserted.
      end
    join
  endtask
  
  // Task to send a command to the DUT and verify that the command is sent.
  task automatic SendCmd(input [15:0] cmd_to_send, ref [15:0] cmd, ref clk, ref send_cmd, ref cmd_sent);
    begin
        // cmd is the command to send.
        cmd = cmd_to_send;

        @(negedge clk) send_cmd = 1'b1; // Assert snd_cmd and begin transmission.
        @(negedge clk) send_cmd = 1'b0; // Deassert snd_cmd after one clock cycle.

        // Wait for 60000 clocks for cmd_sent to be asserted, else timeout.
        TimeoutTask(.sig(cmd_sent), .clk(clk) .clks2wait(60000), .signal("cmd_sent"));
    end
  endtask

  // Task to check if a positive acknowledge is received from the DUT.
  task automatic ChkPosAck(ref resp_rdy, ref clk, ref resp);
    // Wait 60000 clock cycles, and ensure that a response is received.
    TimeoutTask(.sig(resp_rdy), .clk(clk) .clks2wait(60000), .signal("resp_rdy"));

    // Check that a positive acknowledge of 0xA5 is received.
    if (resp !== 8'hA5) begin
      $display("ERROR: resp should have been 8'hA5 but was 0x%h", resp);
      $stop(); 
    end
  endtask

endpackage
