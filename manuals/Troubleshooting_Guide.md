# MVI Edge Troubleshooting Guide

## Common Problems and Solutions

### 1. Connection Issues

#### MQTT Connection Failed
**Symptoms:**
- Cannot connect to MQTT broker
- Connection drops frequently
- Timeout errors

**Solutions:**
1. **Check MQTT Broker**
   ```bash
   # Check if broker is running
   systemctl status mosquitto

   # Restart broker
   sudo systemctl restart mosquitto
   ```

2. **Verify Configuration**
   - Check broker IP address in config.json
   - Verify port (default: 1883)
   - Test connection: `mosquitto_sub -h localhost -t "#"`

3. **Network Issues**
   - Check firewall: `sudo ufw status`
   - Allow MQTT port: `sudo ufw allow 1883`
   - Test ping: `ping <broker-ip>`

4. **Authentication**
   - Verify username/password
   - Check broker ACL settings
   - Try without credentials first

#### Camera Connection Lost
**Solutions:**
- Check USB/network cable
- Verify camera power
- Restart camera service
- Update camera drivers

### 2. Inspection Issues

#### No Image Displayed
**Possible Causes:**
- Image path incorrect
- File permissions
- Network path not accessible
- Image format not supported

**Solutions:**
1. Check image path in MQTT message
2. Verify file exists: `ls -la /path/to/image`
3. Check permissions: `chmod 644 image.jpg`
4. Test with local image first

#### Wrong Detection Results
**Symptoms:**
- Too many false positives
- Missing real defects
- Inconsistent results

**Solutions:**
1. **Adjust Threshold**
   - High false positives → Increase threshold (0.8-0.9)
   - Missing defects → Decrease threshold (0.5-0.6)

2. **Improve Conditions**
   - Check lighting (use diffused, even lighting)
   - Clean camera lens
   - Fix camera focus
   - Ensure consistent object positioning

3. **Retrain Model**
   - Add more training images
   - Include edge cases
   - Balance dataset (pass/fail ratio)
   - Use data augmentation

### 3. Performance Issues

#### Slow Response Time
**Causes:**
- High image resolution
- CPU bottleneck
- Network latency
- Model complexity

**Solutions:**
1. Reduce image resolution (max 1920x1080)
2. Use GPU for inference
3. Optimize network bandwidth
4. Consider lighter model

#### Memory Issues
**Solutions:**
- Restart MVI Edge service
- Clear image cache
- Reduce batch size
- Add more RAM

### 4. Software Issues

#### MVI Edge Not Starting
**Solutions:**
```bash
# Check logs
journalctl -u mvi-edge -n 50

# Check disk space
df -h

# Check dependencies
python3 -m pip list | grep maximo

# Reinstall
pip3 install --upgrade maximo-visual-inspection
```

#### Python Dependencies Error
**Solutions:**
```bash
# Update pip
python3 -m pip install --upgrade pip

# Install requirements
pip3 install -r requirements.txt

# Virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. GUI Application Issues

#### Trigger Timeout
**Causes:**
- MVI Edge not responding
- MQTT topic mismatch
- Network issues

**Solutions:**
1. Check MVI Edge status
2. Verify topic names match
3. Test manual trigger via mosquitto_pub
4. Check subscribe_topic in config

#### Images Not Saving
**Solutions:**
- Check disk space: `df -h`
- Verify permissions on history_images/
- Create directory: `mkdir -p history_images`
- Check logs for errors

## Diagnostic Commands

### Check System Status
```bash
# MQTT Broker
systemctl status mosquitto
mosquitto_sub -h localhost -t "#" -v

# MVI Edge
systemctl status mvi-edge
ps aux | grep mvi

# Disk Space
df -h
du -sh /path/to/images

# Network
ping <broker-ip>
netstat -tlnp | grep 1883
```

### Check Logs
```bash
# Application logs
tail -f *.log

# System logs
journalctl -f

# MQTT logs
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### Test MQTT
```bash
# Subscribe to all topics
mosquitto_sub -h localhost -t "#" -v

# Publish test message
mosquitto_pub -h localhost -t "test/topic" -m '{"test": "message"}'

# Test with authentication
mosquitto_sub -h localhost -u username -P password -t "#"
```

## Prevention Tips

1. **Regular Maintenance**
   - Clean camera lenses weekly
   - Check disk space monthly
   - Update software quarterly
   - Review logs regularly

2. **Monitoring**
   - Set up alerts for connection failures
   - Monitor pass/fail rates
   - Track response times
   - Log all inspections

3. **Documentation**
   - Document configuration changes
   - Keep calibration records
   - Maintain troubleshooting log
   - Track model versions

4. **Backup**
   - Backup configuration files
   - Save trained models
   - Export inspection history
   - Document network setup

## Getting Help

If problems persist:
1. Check documentation: https://www.ibm.com/docs/en/maximo-vi
2. Search community forums
3. Contact support with:
   - Error messages
   - Log files
   - System information
   - Steps to reproduce
